import asyncio
import httpx
from urllib.parse import quote
from typing import Optional, Any

from app.config import RIOT_API_KEY, REGIONAL


PLATFORM = {
  # Americas cluster
  "NA1": "na1", "BR1": "br1", "LA1": "la1", "LA2": "la2", "OC1": "oc1",
  # Europe
  "EUW1": "euw1", "EUN1": "eun1", "TR1": "tr1", "RU": "ru",
  # Asia
  "KR": "kr", "JP1": "jp1",
  # SEA
  "PH2": "ph2", "SG2": "sg2", "TH2": "th2", "TW2": "tw2", "VN2": "vn2",
}


PLATFORM_ALIASES = {
  "NA": "NA1",
  "EUW": "EUW1",
  "EUNE": "EUN1",
  "TR": "TR1",
  "JP": "JP1",
}


class RiotClient:
  def __init__(self):
    self._client: Optional[httpx.AsyncClient] = None

  async def __aenter__(self):
    limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
    self._client = httpx.AsyncClient(timeout=20.0, limits=limits)
    return self

  async def __aexit__(self, *exc):
    if self._client:
      await self._client.aclose()

  @staticmethod
  def _norm_region(region: str) -> str:
    r = (region or "").lower()
    if r not in REGIONAL:
      raise ValueError("region must be one of: americas, europe, asia, sea")
    return r

  def _norm_platform(self, tag_or_code: str) -> str:
    """
    Accept either a Riot ID tag (e.g., 'NA1') or a direct platform code (e.g., 'na1').
    Prefer direct codes; otherwise map known tags; finally default to 'na1'.
    """
    s = (tag_or_code or "").strip()
    if not s:
      return "na1"
    # direct code?
    low = s.lower()
    if low in PLATFORM.values():
      return low
    # tag alias?
    return PLATFORM.get(s.upper(), "na1")

  async def _get(self, url: str, params: dict | None = None) -> Any:
    """GET with basic retry for 429/5xx. Returns JSON (dict or list)."""
    if not RIOT_API_KEY:
      raise RuntimeError("Missing RIOT_API_KEY env var")
    headers = {"X-Riot-Token": RIOT_API_KEY}

    attempts = 0
    while True:
      attempts += 1
      r = await self._client.get(url, headers=headers, params=params)
      if r.status_code == 429:
        retry = int(r.headers.get("Retry-After", "1"))
        await asyncio.sleep(max(1, retry))
        continue
      if r.status_code in (502, 503, 504) and attempts < 3:
        await asyncio.sleep(0.5 * attempts)
        continue
      r.raise_for_status()
      return r.json()

  # -------- Account / PUUID via REGIONAL --------
  async def puuid_by_riot_id(self, region: str, game_name: str, tag_line: str) -> str:
    reg = self._norm_region(region)
    url = (
      f"https://{reg}.api.riotgames.com/riot/account/v1/accounts/"
      f"by-riot-id/{quote(game_name)}/{quote(tag_line)}"
    )
    data = await self._get(url)
    return data["puuid"]

  # -------- Match via REGIONAL (supports time/window + queue) --------
  async def match_ids(
      self,
      region: str,
      puuid: str,
      *,
      start: int = 0,
      count: int = 100,
      start_time: int | None = None,
      end_time: int | None = None,
      queue: int | None = None,        # 420/440/400/430/450/etc.
  ) -> list[str]:
    reg = self._norm_region(region)
    base = (
      f"https://{reg}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    )
    params: dict = {"start": start, "count": count}
    if start_time is not None:
      params["startTime"] = start_time
    if end_time is not None:
      params["endTime"] = end_time
    if queue is not None:
      params["queue"] = queue
    return await self._get(base, params=params)

  async def match(self, region: str, match_id: str) -> dict:
    reg = self._norm_region(region)
    url = f"https://{reg}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    return await self._get(url)

  # --- Rank & Summoner endpoints (platform-scoped) ---
  async def summoner_by_puuid(self, platform: str, puuid: str) -> dict:
    plat = self._norm_platform(platform)
    url = f"https://{plat}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    return await self._get(url)

  async def ranked_entries(self, platform: str, summoner_id: str) -> list[dict]:
    plat = self._norm_platform(platform)
    url = f"https://{plat}.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}"
    return await self._get(url)
