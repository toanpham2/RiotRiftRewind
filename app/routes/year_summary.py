# app/routes/year_summary.py
from __future__ import annotations

import asyncio
import json
import time
import os
import httpx

from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query

from app.bedrock_client import coach_with_claude
from app.config import SPLITS
from app.riot_client import RiotClient
from app.services.split_agg import (
  fetch_matches_since_patch,
  filter_matches_by_split,
  classify_primary_mode,
  filter_matches_by_bucket,
  aggregate_overall_metrics,
  aggregate_champ_table,
)

router = APIRouter(prefix="/api", tags=["year"])

# ----------------------------
# Formatting helpers
# ----------------------------
def _fmt2f(x: float) -> float:
  return float(f"{x:.2f}")

def _fmtpct(x: float) -> str:
  return f"{x * 100:.2f}%"


def _overall_out(overall: Optional[dict]) -> Optional[dict]:
  if not overall:
    return None
  o = dict(overall)
  if isinstance(o.get("winrate"), (int, float)):
    o["winrate"] = _fmtpct(o["winrate"])
  o["kda"] = _fmt2f(o["kda"])
  o["csPerMin"] = _fmt2f(o["csPerMin"])
  o["visionPerMin"] = _fmt2f(o["visionPerMin"])
  return o


def _champ_row_out(r: Optional[dict], pct_fields: List[str] = ("kp", "dmgShare")) -> Optional[dict]:
  if not r:
    return None
  out = dict(r)
  for k in ("kda", "csPerMin", "visionPerMin", "score", "winrate"):
    if k in out and isinstance(out[k], (int, float)):
      out[k] = _fmtpct(out[k]) if k == "winrate" else _fmt2f(out[k])
  for k in pct_fields:
    if k in out and isinstance(out[k], (int, float)):
      out[k] = _fmtpct(out[k])
  return out


def _project_top_champs(rows: List[dict], best_name: Optional[str], limit: int = 3) -> List[dict]:
  out = []
  for r in rows:
    if best_name and r.get("name") == best_name:
      continue
    out.append({
      "name": r.get("name"),
      "role": r.get("role"),
      "games": r.get("games", 0),
      "winrate": r.get("winrate"),
    })
    if len(out) == limit:
      break
  return out


def _top3(rows: List[dict]) -> List[dict]:
  return rows[:3] if rows else []


# ----------------------------
# Majority-role relabel (local, defensive)
# ----------------------------
_POS_MAP = {
  "TOP": "top",
  "JUNGLE": "jungle",
  "MIDDLE": "mid",
  "BOTTOM": "adc",
  "UTILITY": "support",
}

def _extract_position(p: dict) -> str:
  pos = (p.get("teamPosition") or "").upper()
  if pos in _POS_MAP:
    return _POS_MAP[pos]
  lane = (p.get("lane") or "").upper()
  role = (p.get("role") or "").upper()
  if lane == "TOP": return "top"
  if lane == "MIDDLE": return "mid"
  if lane == "JUNGLE": return "jungle"
  if lane == "BOTTOM":
    return "adc" if role in ("CARRY", "DUO_CARRY") else "support"
  return "top"

def _majority_role_for_champ(matches: List[dict], puuid: str, champ_name: str) -> str:
  roles: Dict[str, int] = {}
  for m in matches:
    info = m.get("info", {})
    you = next((p for p in info.get("participants", []) if p.get("puuid") == puuid), None)
    if not you or you.get("championName") != champ_name:
      continue
    role = _extract_position(you)
    roles[role] = roles.get(role, 0) + 1
  if not roles:
    return "top"
  return max(roles.items(), key=lambda kv: kv[1])[0]


# ----------------------------
# Feel-good quote & advice
# ----------------------------
_FEEL_GOOD_SYSTEM = (
  "You are Rift Rewind’s hype writer. Write ONE short, punchy feel-good line "
  "that connects the player to the champion’s identity. No hashtags, no emojis, "
  "no second paragraph, ≤ 28 words."
)

_FEEL_GOOD_FEWSHOT = [
  ("Pantheon", "Pantheon isn’t just your best champ — he mirrors your will. Every game you prove you’re as relentless as the Unbreakable Spear."),
  ("Aatrox",   "Aatrox isn’t just your weapon — he’s your unyielding drive. Every swing reminds enemies you’re as relentless as the Darkin Blade."),
  ("Renekton", "Renekton matches your ferocity — decisive, fearless, dominant. You swing games with the Butcher’s fury."),
  ("Gwen",     "Gwen reflects your precision — every cut stitched to win. You weave fights like the Hallowed Seamstress."),
  ("Soraka",   "Soraka fits your calm strength — steady, clutch, saving fights. You guide your team like the Starchild."),
]

def _feel_good_prompt(player: str, champ: str) -> str:
  examples = "\n".join([f"{c}: {q}" for c, q in _FEEL_GOOD_FEWSHOT])
  return json.dumps({
    "player": player,
    "champion": champ,
    "style_examples": examples,
    "instructions": "Write one new line in the same tone tailored to this champion and player."
  }, ensure_ascii=False)

async def _summoner_id_from_recent_match(region: str, puuid: str) -> tuple[Optional[str], dict]:
  """
  Resolve encryptedSummonerId by inspecting the latest match's participants.
  Returns (summonerId_or_None, debug_dict).
  """
  dbg = {"__midProbeStatus": None, "__summIdFromMatch": False}
  try:
    async with RiotClient() as rc:
      ids = await rc.match_ids(region, puuid, start=0, count=1)
      if not ids:
        dbg["__midProbeStatus"] = "no_match_ids"
        return (None, dbg)
      mid = ids[0]
      m = await rc.match(region, mid)
      info = (m or {}).get("info", {})
      you = next((p for p in info.get("participants", []) if p.get("puuid") == puuid), None)
      sid = (you or {}).get("summonerId")
      if sid:
        dbg["__midProbeStatus"] = "ok"
        dbg["__summIdFromMatch"] = True
        return (sid, dbg)
      dbg["__midProbeStatus"] = "no_participant_sid"
      return (None, dbg)
  except Exception as e:
    dbg["__midProbeStatus"] = f"err:{str(e)[:160]}"
    return (None, dbg)


def _generate_feel_good(player: str, champ: str) -> str:
  try:
    raw = coach_with_claude(_FEEL_GOOD_SYSTEM, _feel_good_prompt(player, champ),
                            max_tokens=70, temperature=0.6)
    return raw.strip().strip('"').splitlines()[0].strip()[:220]
  except Exception:
    return f"{champ} fits you—decisive, confident, and clutch. Keep leaning into what makes your playstyle win."

def _claude_year_advice(payload: dict) -> dict:
  system = (
    "You are Rift Rewind, a precise League of Legends YEAR analyst.\n"
    "Input is structured stats for the full year (primary queue subset already chosen).\n"
    "Return STRICT JSON with keys: summary, insights, focus, fun.\n"
    "- summary: <= 50 words across 2 sentences; use 'Year' (never 'Season').\n"
    "- insights: 5–6 concise bullets; be role-aware (support=vision; jungle=KP/objectives; lanes=CS/KDA/damage).\n"
    "- focus: 5 measurable targets.\n"
    "- fun: one playful line; prefer payload.funStat details if present.\n"
    "If gamesAnalyzed < 10, emphasize consistency & sample size."
  )
  user = json.dumps(payload, ensure_ascii=False)
  try:
    raw = coach_with_claude(system, user, max_tokens=700, temperature=0.4)
    return json.loads(raw)
  except Exception:
    fun_line = "Queue up and have fun — lock 1–2 champs, stabilize role, and let fundamentals carry."
    fs = payload.get("funStat", {})
    if isinstance(fs, dict) and fs.get("text"):
      fun_line = fs["text"].replace("We’ve all been there.", "At least you committed to the play!")
    return {
      "summary": "Small sample or AI unavailable — here’s a quick year plan.",
      "insights": [
        "Stabilize champion pool and role for consistent execution.",
        "Nudge CS/vision to lane-appropriate baselines.",
        "Trim deaths in mid-game skirmishes."
      ],
      "focus": [
        "Play 20 games in one role",
        "CS/min ≥ 6.5 (laner) or Vision ≥ 0.9/min (support)",
        "≤4 deaths/game over next 15 games"
      ],
      "fun": fun_line
    }


# ----------------------------
# Tiny in-memory TTL cache (also cache final responses)
# ----------------------------
class TTLCache:
  def __init__(self) -> None:
    self._m: Dict[str, tuple[float, Any]] = {}

  def get(self, k: str) -> Any | None:
    v = self._m.get(k)
    if not v:
      return None
    exp, payload = v
    if time.time() > exp:
      self._m.pop(k, None)
      return None
    return payload

  def put(self, k: str, payload: Any, ttl: int = 300) -> None:
    self._m[k] = (time.time() + ttl, payload)

CACHE = TTLCache()


async def _cached_puuid(region: str, name: str, tag: str) -> str:
  key = f"puuid:{region}:{name}#{tag}"
  hit = CACHE.get(key)
  if hit:
    return hit
  async with RiotClient() as rc:
    puuid = await rc.puuid_by_riot_id(region, name, tag)
  CACHE.put(key, puuid, ttl=3600)
  return puuid


async def _cached_all_matches(region: str, puuid: str) -> List[dict]:
  earliest_lo = min(lo for (lo, _hi) in SPLITS.values())
  key = f"matches_all:{region}:{puuid}:{earliest_lo}"
  hit = CACHE.get(key)
  if hit is not None:
    return hit
  matches = await fetch_matches_since_patch(region, puuid, earliest_lo)
  CACHE.put(key, matches, ttl=900)
  return matches


# ----------------------------
# Platform/Region maps
# ----------------------------
REGION_TO_PLATFORMS = {
  "americas": ["na1", "br1", "la1", "la2", "oc1"],
  "europe":   ["euw1", "eun1", "tr1", "ru"],
  "asia":     ["kr", "jp1"],
  "sea":      ["ph2", "sg2", "th2", "tw2", "vn2"],
}
ALL_PLATFORMS_IN_ORDER = (
    REGION_TO_PLATFORMS["americas"]
    + REGION_TO_PLATFORMS["europe"]
    + REGION_TO_PLATFORMS["asia"]
    + REGION_TO_PLATFORMS["sea"]
)

async def _resolve_region_for_riot_id(game_name: str, tag_line: str) -> Optional[str]:
  for reg in ("americas", "europe", "asia", "sea"):
    try:
      async with RiotClient() as rc:
        _ = await rc.puuid_by_riot_id(reg, game_name, tag_line)
      return reg
    except Exception:
      continue
  return None


async def _derive_platform_from_activity(region: str, puuid: str) -> Optional[str]:
  async with RiotClient() as rc:
    try:
      ids = await rc.match_ids(region, puuid, start=0, count=1)
      if ids:
        mid = ids[0]
        if "_" in mid:
          prefix = mid.split("_", 1)[0].lower()
          return prefix
    except Exception:
      pass
  plats = REGION_TO_PLATFORMS.get(region, [])
  async with RiotClient() as rc:
    for plat in plats:
      try:
        summ = await rc.summoner_by_puuid(plat, puuid)
        if summ and "id" in summ:
          return plat
      except Exception:
        continue
  return None


# ----------------------------
# Ranked lookup (expanded probing)
# ----------------------------
_TIER_ORDER = {
  "CHALLENGER": 9, "GRANDMASTER": 8, "MASTER": 7,
  "DIAMOND": 6, "EMERALD": 5, "PLATINUM": 4,
  "GOLD": 3, "SILVER": 2, "BRONZE": 1, "IRON": 0,
}
_DIV_ORDER = {"I": 3, "II": 2, "III": 1, "IV": 0}

def _rank_score(entry: dict) -> tuple:
  tier = (entry.get("tier") or "").upper()
  div  = (entry.get("rank") or "").upper()
  lp   = int(entry.get("leaguePoints", 0) or 0)
  return (_TIER_ORDER.get(tier, -1), _DIV_ORDER.get(div, -1), lp)

def _pick_best_entry(entries: List[dict]) -> Optional[dict]:
  if not entries:
    return None
  solo = [e for e in entries if e.get("queueType") == "RANKED_SOLO_5x5"]
  flex = [e for e in entries if e.get("queueType") == "RANKED_FLEX_SR"]
  cands = solo or flex or []
  return max(cands, key=_rank_score) if cands else None

async def _entries_on_platform(plat: str, puuid: str) -> Tuple[Optional[str], List[dict]]:
  try:
    async with RiotClient() as rc:
      summ = await rc.summoner_by_puuid(plat, puuid)
      summ_id = (summ or {}).get("id")
      if not summ_id:
        return None, []
      try:
        entries = await rc.ranked_entries(plat, summ_id)
      except Exception:
        entries = []
      return summ_id, entries or []
  except Exception:
    return None, []

async def _league_entries_direct(platform: str, summ_id: str) -> List[dict]:
  api_key = os.getenv("RIOT_API_KEY")
  if not api_key:
    return []
  url = f"https://{platform}.api.riotgames.com/lol/league/v4/entries/by-summoner/{summ_id}"
  headers = {"X-Riot-Token": api_key}
  timeout = httpx.Timeout(5.0, connect=5.0)
  async with httpx.AsyncClient(timeout=timeout) as client:
    r = await client.get(url, headers=headers)
    if r.status_code == 200:
      try:
        data = r.json()
        return data if isinstance(data, list) else []
      except Exception:
        return []
    return []

async def _direct_summoner_by_puuid(platform: str, puuid: str) -> tuple[Optional[str], dict]:
  """
  Direct call to the platform host to resolve encrypted summonerId from puuid.
  Returns (summoner_id_or_None, debug_dict).
  """
  url = f"https://{platform}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
  headers = {"X-Riot-Token": os.getenv("RIOT_API_KEY")}
  timeout = httpx.Timeout(7.0, connect=5.0)
  debug = {"__summHttpStatus": None, "__summHttpBodyPreview": None}

  try:
    async with httpx.AsyncClient(timeout=timeout) as c:
      r = await c.get(url, headers=headers)
      debug["__summHttpStatus"] = r.status_code
      body = r.text or ""
      debug["__summHttpBodyPreview"] = body[:250]
      if r.status_code == 200:
        data = r.json()
        return (data.get("id"), debug)
  except Exception as e:
    debug["__summHttpBodyPreview"] = f"direct_err: {str(e)[:200]}"
  return (None, debug)

async def _cached_current_rank(
    platform: str,
    puuid: str,
    *,
    forcePlatform: Optional[str] = None,
    region_hint: Optional[str] = None,
    debug: bool = False,
) -> dict:
  plat = (forcePlatform or platform or "").lower()
  out = {"queue": "UNRANKED", "tier": None, "division": None, "lp": 0, "wins": 0, "losses": 0}
  dbg = {"__chosenPlatform": plat, "__regionHint": region_hint}

  if not plat:
    if debug: out.update(dbg)
    return out

  cache_key = f"rank:{plat}:{puuid}"
  hit = CACHE.get(cache_key)
  if hit and not debug:
    return hit

  # --- 0) Try to recover encryptedSummonerId from a recent match (most reliable)
  summ_id = None
  mid_dbg = {}
  sid_from_match, mid_dbg = await _summoner_id_from_recent_match(region_hint or "americas", puuid)
  if sid_from_match:
    summ_id = sid_from_match

  # --- 1) If not found, try via RiotClient summoner-by-puuid on platform
  client_summ_err = None
  if not summ_id:
    async with RiotClient() as rc:
      try:
        summ = await rc.summoner_by_puuid(plat, puuid)
        summ_id = (summ or {}).get("id")
      except Exception as e:
        client_summ_err = str(e)[:200]

  # --- 2) If still not found, try your direct HTTP call
  direct_dbg = {}
  if not summ_id:
    try:
      sid, direct_dbg = await _direct_summoner_by_puuid(plat, puuid)
      summ_id = sid
    except Exception as _:
      pass

  if debug:
    dbg["__summonerId"] = bool(summ_id)
    dbg["__summFromMatch"] = mid_dbg.get("__summIdFromMatch", False)
    dbg["__midProbeStatus"] = mid_dbg.get("__midProbeStatus")
    dbg["__summonerClientErr"] = client_summ_err
    dbg.update({k: v for k, v in direct_dbg.items() if k.startswith("__summ")})

  if not summ_id:
    if debug: out.update(dbg)
    return out

  # --- 3) Fetch league entries (client first, then direct)
  entries = []
  client_rank_err = None

  async with RiotClient() as rc:
    try:
      entries = await rc.ranked_entries_by_puuid(plat, puuid)
    except Exception as e:
      client_rank_err = str(e)[:200]
      entries = []

  # direct fallback (also by PUUID), in case your client class hit a transient error
  http_status = None
  http_preview = None
  if not entries:
    try:
      import httpx, os
      url = f"https://{plat}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
      headers = {"X-Riot-Token": os.getenv("RIOT_API_KEY")}
      timeout = httpx.Timeout(7.0, connect=5.0)
      async with httpx.AsyncClient(timeout=timeout) as c:
        r = await c.get(url, headers=headers)
        http_status = r.status_code
        body = r.text or ""
        http_preview = body[:250]
        if r.status_code == 200 and isinstance(r.json(), list):
          entries = r.json()
    except Exception as e:
      http_preview = f"direct_err: {str(e)[:200]}"

  if debug:
    dbg["__rankClientError"] = client_rank_err
    dbg["__rankHttpStatus"] = http_status
    dbg["__rankHttpBodyPreview"] = http_preview

  # --- 4) Choose SOLO first, else FLEX
  chosen = None
  for e in entries or []:
    if e.get("queueType") == "RANKED_SOLO_5x5":
      chosen = e; break
  if not chosen:
    for e in entries or []:
      if e.get("queueType") == "RANKED_FLEX_SR":
        chosen = e; break

  if chosen:
    out = {
      "queue": chosen.get("queueType"),
      "tier": chosen.get("tier"),
      "division": chosen.get("rank"),
      "lp": chosen.get("leaguePoints", 0),
      "wins": chosen.get("wins", 0),
      "losses": chosen.get("losses", 0),
    }

  if not debug:
    CACHE.put(cache_key, out, ttl=600)
  else:
    out.update(dbg)
  return out


# ----------------------------
# Best/Worst game helpers
# ----------------------------
def _find_best_game(matches: List[dict], puuid: str) -> Optional[Tuple[str, int, int, int]]:
  best = None
  for m in matches:
    info = m.get("info", {})
    you = next((p for p in info.get("participants", []) if p.get("puuid") == puuid), None)
    if not you:
      continue
    k = you.get("kills", 0)
    d = you.get("deaths", 0)
    a = you.get("assists", 0)
    champ = you.get("championName", "Unknown")
    denom = max(1, d)
    kda = (k + a) / denom
    key = (kda, k)
    if (best is None) or (key > best[0]):
      best = ((kda, k), (champ, k, d, a))
  return best[1] if best else None


def _format_kda(k: int, d: int, a: int) -> str:
  return f"{k}/{d}/{a}"


def _year_fun_stat(matches: List[dict], puuid: str) -> Optional[dict]:
  worst = None
  for m in matches:
    info = m.get("info", {})
    you = next((p for p in info.get("participants", []) if p.get("puuid") == puuid), None)
    if not you:
      continue
    deaths = you.get("deaths", 0)
    if (worst is None) or (deaths > worst["deaths"]):
      worst = {
        "deaths": deaths,
        "k": you.get("kills", 0),
        "a": you.get("assists", 0),
        "champ": you.get("championName", "Unknown"),
      }
  if not worst:
    return None
  return {
    "kind": "oops",
    "text": f"Most deaths game: {worst['deaths']} on {worst['champ']} ({worst['k']}/{worst['deaths']}/{worst['a']}). We’ve all been there."
  }


def _best_game_quote(player: str, champ: str, kda_str: str) -> str:
  system = (
    "You are Rift Rewind. Write ONE short, punchy praise line for the player's BEST game. "
    "Include the champion and K/D/A. ≤ 26 words. No emojis."
  )
  user = json.dumps({
    "player": player,
    "champion": champ,
    "kda": kda_str,
    "style": "confident, triumphant, not cringe"
  })
  try:
    raw = coach_with_claude(system, user, max_tokens=60, temperature=0.5)
    return raw.strip().strip('"').splitlines()[0].strip()[:200]
  except Exception:
    return f"{champ} clinic — {kda_str}. Clean, clinical, clutch."


# ----------------------------
# Assemble one split block (no split-level fun/standout)
# ----------------------------
def _build_split_block(split_id: str, all_matches: List[dict], puuid: str) -> dict:
  lo, hi = SPLITS[split_id]
  patch_range = f"{lo} - {hi}"
  raw_matches = filter_matches_by_split(all_matches, split_id)
  if not raw_matches:
    return {
      "splitId": split_id,
      "patchRange": patch_range,
      "gamesAnalyzed": 0,
      "primaryQueue": "unranked",
      "overall": None,
      "bestChamp": None,
      "topChamps": [],
    }

  primary_info = classify_primary_mode(raw_matches)
  dist = primary_info.get("dist", {})
  primary_bucket = primary_info.get("primary") or (max(dist.items(), key=lambda kv: kv[1])[0] if dist else "unranked")

  bucket_matches = (
    filter_matches_by_bucket(raw_matches, primary_bucket)
    if primary_bucket and primary_bucket != "unranked" else raw_matches
  )

  overall = aggregate_overall_metrics(bucket_matches, puuid)
  table = aggregate_champ_table(bucket_matches, puuid)

  relabeled = []
  for row in table:
    champ = row.get("name")
    role = _majority_role_for_champ(bucket_matches, puuid, champ)
    new_row = dict(row)
    new_row["role"] = role
    relabeled.append(new_row)

  relabeled.sort(key=lambda r: r["score"], reverse=True)
  best = relabeled[0] if relabeled else None

  best_fmt = _champ_row_out(best)
  overall_fmt = _overall_out(overall)
  top3_fmt_full = [_champ_row_out(r) for r in _top3(relabeled)]
  top_champs = _project_top_champs(top3_fmt_full, best_fmt.get("name") if best_fmt else None, limit=3)

  return {
    "splitId": split_id,
    "patchRange": patch_range,
    "gamesAnalyzed": len(bucket_matches),
    "primaryQueue": primary_bucket,
    "overall": overall_fmt,
    "bestChamp": best_fmt,
    "topChamps": top_champs,
  }


# ----------------------------
# Year summary endpoint
# ----------------------------
@router.get("/year-summary")
async def year_summary(
    region: Optional[str] = None,
    riotId: str = "",
    includeFeelGood: bool = True,
    includeAdvice: bool = True,
    debugRank: bool = Query(False, description="Include rank platform probing details"),
    forcePlatform: Optional[str] = None
):
  if "#" not in riotId and "%23" not in riotId:
    raise HTTPException(400, "riotId must be Name#TAG (e.g., MK1Paris#NA1)")
  name, tag = riotId.replace("%23", "#").split("#", 1)

  cache_key_resp = f"yearresp:{region}:{riotId}:{includeFeelGood}:{includeAdvice}:{debugRank}"
  hit_resp = CACHE.get(cache_key_resp)
  if hit_resp is not None:
    return hit_resp

  # 1) region
  reg = (region or "").strip().lower()
  if reg not in ("americas", "europe", "asia", "sea"):
    reg = await _resolve_region_for_riot_id(name, tag)
    if not reg:
      raise HTTPException(404, "Could not resolve regional cluster for this Riot ID.")

  # 2) PUUID + parallelize platform + matches
  puuid = await _cached_puuid(reg, name, tag)
  matches_task = asyncio.create_task(_cached_all_matches(reg, puuid))
  platform_task = asyncio.create_task(_derive_platform_from_activity(reg, puuid))
  all_matches, platform = await asyncio.gather(matches_task, platform_task)

  # 3) splits
  split_build_tasks = [asyncio.to_thread(_build_split_block, s, all_matches, puuid) for s in SPLITS.keys()]
  split_block_list = await asyncio.gather(*split_build_tasks)
  split_blocks = { s: block for s, block in zip(SPLITS.keys(), split_block_list) }

  # 4) year
  if not all_matches:
    resp = {
      "splits": split_blocks,
      "year": {
        "primaryQueue": "unranked",
        "gamesAnalyzed": 0,
        "overall": None,
        "bestChamp": None,
        "topChamps": [],
        "funStat": None,
        "bestGame": None,
        "bestGameQuote": None,
        "feelGood": None,
        "advice": None,
      }
    }
    if platform:
      resp["currentRank"] = await _cached_current_rank(platform, puuid, region_hint=reg, debug=debugRank)
    CACHE.put(cache_key_resp, resp, ttl=300)
    return resp

  primary_info_y = classify_primary_mode(all_matches)
  dist_y = primary_info_y.get("dist", {})
  primary_bucket_y = primary_info_y.get("primary") or (max(dist_y.items(), key=lambda kv: kv[1])[0] if dist_y else "unranked")

  bucket_matches_y = (
    filter_matches_by_bucket(all_matches, primary_bucket_y)
    if primary_bucket_y != "unranked" else all_matches
  )

  overall_raw = aggregate_overall_metrics(bucket_matches_y, puuid)
  overall_y = _overall_out(overall_raw)

  table_y = aggregate_champ_table(bucket_matches_y, puuid)
  relabeled_y = []
  for row in table_y:
    champ = row.get("name")
    role = _majority_role_for_champ(bucket_matches_y, puuid, champ)
    new_row = dict(row)
    new_row["role"] = role
    relabeled_y.append(new_row)
  relabeled_y.sort(key=lambda r: r["score"], reverse=True)

  best_y = relabeled_y[0] if relabeled_y else None
  best_y_fmt = _champ_row_out(best_y)
  top3_y_fmt_full = [_champ_row_out(r) for r in _top3(relabeled_y)]
  top3_y_fmt = _project_top_champs(top3_y_fmt_full, best_y_fmt.get("name") if best_y_fmt else None, limit=3)

  # fun/best game
  fun_y = _year_fun_stat(bucket_matches_y, puuid)
  def _find_best_game(matches: List[dict], puuid: str) -> Optional[Tuple[str, int, int, int]]:
    best = None
    for m in matches:
      info = m.get("info", {})
      you = next((p for p in info.get("participants", []) if p.get("puuid") == puuid), None)
      if not you:
        continue
      k = you.get("kills", 0); d = you.get("deaths", 0); a = you.get("assists", 0)
      champ = you.get("championName", "Unknown")
      denom = max(1, d); kda = (k + a) / denom
      key = (kda, k)
      if (best is None) or (key > best[0]):
        best = ((kda, k), (champ, k, d, a))
    return best[1] if best else None

  best_game = _find_best_game(bucket_matches_y, puuid)
  best_game_out = None
  best_game_quote = None
  if best_game:
    bg_champ, bg_k, bg_d, bg_a = best_game
    kda_str = f"{bg_k}/{bg_d}/{bg_a}"
    best_game_out = {"champion": bg_champ, "kda": kda_str}
    best_game_quote = _best_game_quote(f"{name}#{tag}", bg_champ, kda_str)

  # LLM bits
  feel_good = None
  if includeFeelGood:
    player_display = f"{name}#{tag}"
    best_champ_name = (best_y or {}).get("name", "Your Main")
    feel_good = _generate_feel_good(player_display, best_champ_name)

  advice = None
  if includeAdvice:
    advice_payload = {
      "period": "year",
      "primaryQueue": primary_bucket_y,
      "gamesAnalyzed": len(bucket_matches_y),
      "overall": overall_raw,
      "bestChamp": best_y,
      "topChamps": relabeled_y[:3],
      "funStat": fun_y,
      "bestGame": best_game_out,
    }
    advice = _claude_year_advice(advice_payload)

  resp = {
    "splits": split_blocks,
    "year": {
      "primaryQueue": primary_bucket_y,
      "gamesAnalyzed": len(bucket_matches_y),
      "overall": overall_y,
      "bestChamp": best_y_fmt,
      "topChamps": top3_y_fmt,
      "funStat": fun_y,
      "bestGame": best_game_out,
      "bestGameQuote": best_game_quote,
      "feelGood": feel_good,
      "advice": advice,
    }
  }


  if platform or forcePlatform:
    resp["currentRank"] = await _cached_current_rank(
        platform or forcePlatform,
        puuid,
        forcePlatform=forcePlatform,
        region_hint=reg,
        debug=debugRank,
        )

  CACHE.put(cache_key_resp, resp, ttl=300)
  return resp