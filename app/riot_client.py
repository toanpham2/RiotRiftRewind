import asyncio
import httpx
from urllib.parse import quote
from app.config import RIOT_API_KEY, REGIONAL

class RiotClient:
  def __init__(self):
    self._client = None

  async def __aenter__(self):
    # Reuse connections & set a small pool for speed when fetching many matches
    limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
    self._client = httpx.AsyncClient(timeout=20, limits=limits)
    return self

  async def __aexit__(self, *exc):
    if self._client:
      await self._client.aclose()

  @staticmethod
  def _norm_region(region: str) -> str:
    r = (region or "").lower()
    if r not in REGIONAL:
      raise ValueError("must be americas, europe, asia, sea")
    return r

  async def _get(self, url: str) -> dict:
    if not RIOT_API_KEY:
      raise RuntimeError("Missing RIOT_API_KEY env var")
    headers = {"X-Riot-Token": RIOT_API_KEY}
    r = await self._client.get(url, headers=headers)
    if r.status_code == 429:
      retry = int(r.headers.get("Retry-After", "1"))
      await asyncio.sleep(retry)
      r = await self._client.get(url, headers=headers)
    r.raise_for_status()
    return r.json()

  async def puuid_by_riot_id(self, region: str, game_name: str, tag_line: str) -> str:
    reg = self._norm_region(region)
    url = f"https://{reg}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{quote(game_name)}/{quote(tag_line)}"
    data = await self._get(url)
    return data["puuid"]

  async def match_ids(self, region: str, puuid: str, start: int, count: int, queue: int | None = None) -> list[str]:
    reg = self._norm_region(region)
    q = f"&queue={queue}" if queue is not None else ""
    url = f"https://{reg}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count={count}{q}"
    return await self._get(url)

  async def match(self, region: str, match_id: str) -> dict:
    reg = self._norm_region(region)
    url = f"https://{reg}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    return await self._get(url)
