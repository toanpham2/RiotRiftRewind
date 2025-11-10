# app/util/riot_client.py
import asyncio
import httpx
import time
from urllib.parse import quote
from typing import Optional, Any, Dict, Tuple

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

PLATFORM_ALIASES = {"NA": "NA1", "EUW": "EUW1", "EUNE": "EUN1", "TR": "TR1", "JP": "JP1"}

# ----------------------------
# Global async token bucket (100 req / 120s ~= 0.83 rps → use 0.80 for buffer)
# ----------------------------
class _AsyncTokenBucket:
  def __init__(self, rate_per_sec: float, capacity: int):
    self.rate = rate_per_sec
    self.capacity = capacity
    self.tokens = capacity
    self.updated = time.monotonic()
    self.lock = asyncio.Lock()

  async def acquire(self):
    while True:
      async with self.lock:
        now = time.monotonic()
        elapsed = now - self.updated
        self.updated = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        if self.tokens >= 1.0:
          self.tokens -= 1.0
          return
      # sleep outside lock to let others progress
      await asyncio.sleep(0.2)

# 0.80 rps, allow small bursts up to 20 tokens
_GLOBAL_BUCKET = _AsyncTokenBucket(rate_per_sec=0.80, capacity=20)

# ----------------------------
# Simple TTL cache + in-flight coalescing per-process
# ----------------------------
class _TTLCache:
  def __init__(self):
    self._m: Dict[str, Tuple[float, Any]] = {}
    self._locks: Dict[str, asyncio.Future] = {}

  def get(self, k: str):
    v = self._m.get(k)
    if not v:
      return None
    exp, payload = v
    if time.time() > exp:
      self._m.pop(k, None)
      return None
    return payload

  def put(self, k: str, payload: Any, ttl: int):
    self._m[k] = (time.time() + ttl, payload)

  def inflight_get_or_create(self, k: str) -> Optional[asyncio.Future]:
    return self._locks.get(k)

  def inflight_set(self, k: str) -> asyncio.Future:
    fut = asyncio.get_event_loop().create_future()
    self._locks[k] = fut
    return fut

  def inflight_resolve(self, k: str, value: Any = None, exc: BaseException = None):
    fut = self._locks.pop(k, None)
    if fut and not fut.done():
      if exc:
        fut.set_exception(exc)
      else:
        fut.set_result(value)

_CACHE = _TTLCache()

class RiotClient:
  def __init__(self):
    self._client: Optional[httpx.AsyncClient] = None

  async def __aenter__(self):
    limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
    # Small connect timeout; generous read timeout because match bodies are a bit larger
    self._client = httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0), limits=limits)
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
    s = (tag_or_code or "").strip()
    if not s:
      return "na1"
    low = s.lower()
    if low in PLATFORM.values():
      return low
    return PLATFORM.get(s.upper(), "na1")

  async def _get(self, url: str, *, params: dict | None = None, cache_key: str | None = None, ttl: int = 0) -> Any:
    """
    GET with:
      - global token bucket pacing,
      - backoff for 429/5xx,
      - optional TTL caching,
      - in-flight coalescing.
    """
    if not RIOT_API_KEY:
      raise RuntimeError("Missing RIOT_API_KEY env var")

    # Cache hit?
    if cache_key:
      hit = _CACHE.get(cache_key)
      if hit is not None:
        return hit
      inflight = _CACHE.inflight_get_or_create(cache_key)
      if inflight:
        return await inflight  # share the same request

    # mark inflight
    fut = None
    if cache_key:
      fut = _CACHE.inflight_set(cache_key)

    try:
      headers = {"X-Riot-Token": RIOT_API_KEY}
      attempts = 0
      while True:
        attempts += 1
        await _GLOBAL_BUCKET.acquire()
        r = await self._client.get(url, headers=headers, params=params)
        if r.status_code == 429:
          retry = int(r.headers.get("Retry-After", "2"))
          await asyncio.sleep(max(1, retry))
          continue
        if r.status_code in (502, 503, 504) and attempts < 3:
          await asyncio.sleep(0.5 * attempts)
          continue
        r.raise_for_status()
        data = r.json()
        if cache_key and ttl > 0:
          _CACHE.put(cache_key, data, ttl=ttl)
        if fut and not fut.done():
          fut.set_result(data)
        return data
    except BaseException as e:
      if fut and not fut.done():
        fut.set_exception(e)
      raise

  # -------- Account / PUUID via REGIONAL --------
  async def puuid_by_riot_id(self, region: str, game_name: str, tag_line: str) -> str:
    reg = self._norm_region(region)
    url = f"https://{reg}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{quote(game_name)}/{quote(tag_line)}"
    cache_key = f"acc:{reg}:{game_name}#{tag_line}"
    data = await self._get(url, cache_key=cache_key, ttl=3600)
    return data["puuid"]

  # -------- Match IDs via REGIONAL --------
  async def match_ids(
      self,
      region: str,
      puuid: str,
      *,
      start: int = 0,
      count: int = 100,
      start_time: int | None = None,
      end_time: int | None = None,
      queue: int | None = None,
  ) -> list[str]:
    reg = self._norm_region(region)
    base = f"https://{reg}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    params: dict = {"start": start, "count": count}
    if start_time is not None:
      params["startTime"] = start_time
    if end_time is not None:
      params["endTime"] = end_time
    if queue is not None:
      params["queue"] = queue
    cache_key = f"mids:{reg}:{puuid}:{start}:{count}:{start_time}:{end_time}:{queue}"
    return await self._get(base, params=params, cache_key=cache_key, ttl=120)

  # -------- Match detail via REGIONAL --------
  async def match(self, region: str, match_id: str) -> dict:
    reg = self._norm_region(region)
    url = f"https://{reg}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    cache_key = f"match:{reg}:{match_id}"
    return await self._get(url, cache_key=cache_key, ttl=3600)

  # --- Summoner & League (platform-scoped) ---
  async def summoner_by_puuid(self, platform: str, puuid: str) -> dict:
    plat = self._norm_platform(platform)
    url = f"https://{plat}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    cache_key = f"summ:{plat}:{puuid}"
    return await self._get(url, cache_key=cache_key, ttl=3600)

  async def ranked_entries(self, platform: str, summoner_id: str) -> list[dict]:
    plat = self._norm_platform(platform)
    url = f"https://{plat}.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}"
    cache_key = f"rank_sid:{plat}:{summoner_id}"
    data = await self._get(url, cache_key=cache_key, ttl=300)
    return data if isinstance(data, list) else []

  async def ranked_entries_by_puuid(self, platform: str, puuid: str) -> list[dict]:
    plat = (platform or "").lower()
    url = f"https://{plat}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
    cache_key = f"rank_puuid:{plat}:{puuid}"
    data = await self._get(url, cache_key=cache_key, ttl=300)
    return data if isinstance(data, list) else []
