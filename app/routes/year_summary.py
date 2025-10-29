from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from app.bedrock_client import coach_with_claude
from app.config import SPLITS
from app.riot_client import RiotClient
from app.services.split_agg import (
  fetch_matches_since_patch,
  filter_matches_by_split,
  classify_primary_mode,
  filter_matches_by_bucket,
  aggregate_overall_metrics,
  aggregate_best_champ,
  aggregate_champ_table,
  pick_standout_metric_overall,
  fun_stat_from_matches,
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

def _top3(rows: List[dict]) -> List[dict]:
  return rows[:3] if rows else []

# ----------------------------
# Feel-good quote (few-shot) — rank intentionally NOT included
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

def _generate_feel_good(player: str, champ: str) -> str:
  try:
    raw = coach_with_claude(_FEEL_GOOD_SYSTEM, _feel_good_prompt(player, champ),
                            max_tokens=70, temperature=0.6)
    return raw.strip().strip('"').splitlines()[0].strip()[:220]
  except Exception:
    return f"{champ} fits you—decisive, confident, and clutch. Keep leaning into what makes your playstyle win."

# ----------------------------
# Year advice (LLM) – mirrors split advice but year-scoped
# ----------------------------
def _claude_year_advice(payload: dict) -> dict:
  system = (
    "You are Rift Rewind, a precise League of Legends YEAR analyst.\n"
    "Input is structured stats for the full year (primary queue subset already chosen).\n"
    "Return STRICT JSON with keys: summary, insights, focus, fun.\n"
    "- summary: <= 50 words across 2 sentences; use 'Year' (never 'Season').\n"
    "- insights: 5–6 concise bullets; be role-aware (support=vision; jungle=KP/objectives; lanes=CS/KDA/damage).\n"
    "- focus: 5 measurable targets (e.g., 'CS/min ≥ 6.5 over next 20 games', 'Vision ≥ 0.6/min', 'Deaths ≤ 4/game').\n"
    "- fun: one playful line; prefer payload.funStat details if present.\n"
    "If gamesAnalyzed < 10, emphasize consistency & sample size."
  )
  user = json.dumps(payload, ensure_ascii=False)
  try:
    raw = coach_with_claude(system, user, max_tokens=700, temperature=0.4)
    return json.loads(raw)
  except Exception:
    # Safe fallback
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
# Tiny in-memory TTL cache
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
# Auto-routing helpers
# ----------------------------
REGION_TO_PLATFORMS = {
  "americas": ["na1", "br1", "la1", "la2", "oc1"],
  "europe":   ["euw1", "eun1", "tr1", "ru"],
  "asia":     ["kr", "jp1"],
  "sea":      ["ph2", "sg2", "th2", "tw2", "vn2"],
}

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

async def _cached_current_rank(platform: str, puuid: str) -> dict:
  key = f"rank:{platform}:{puuid}"
  hit = CACHE.get(key)
  if hit:
    return hit
  async with RiotClient() as rc:
    try:
      summ = await rc.summoner_by_puuid(platform, puuid)
      summ_id = (summ or {}).get("id")
    except Exception:
      summ_id = None
    rank = {"queue": "UNRANKED", "tier": None, "division": None, "lp": 0, "wins": 0, "losses": 0}
    if summ_id:
      try:
        entries = await rc.ranked_entries(platform, summ_id)
      except Exception:
        entries = []
      def pick(q: str):
        for e in entries or []:
          if e.get("queueType") == q:
            return e
        return None
      chosen = pick("RANKED_SOLO_5x5") or pick("RANKED_FLEX_SR")
      if chosen:
        rank = {
          "queue": chosen.get("queueType"),
          "tier": chosen.get("tier"),
          "division": chosen.get("rank"),
          "lp": chosen.get("leaguePoints", 0),
          "wins": chosen.get("wins", 0),
          "losses": chosen.get("losses", 0),
        }
  CACHE.put(key, rank, ttl=600)
  return rank

# ----------------------------
# Assemble one split block from a pre-fetched pool
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
      "standout": None,
      "topChamps": [],
      "funStat": None,
    }
  primary_info = classify_primary_mode(raw_matches)
  dist = primary_info.get("dist", {})
  primary_bucket = primary_info.get("primary") or (max(dist.items(), key=lambda kv: kv[1])[0] if dist else "unranked")
  bucket_matches = (
    filter_matches_by_bucket(raw_matches, primary_bucket)
    if primary_bucket and primary_bucket != "unranked" else raw_matches
  )
  overall = aggregate_overall_metrics(bucket_matches, puuid)
  best = aggregate_best_champ(bucket_matches, puuid)
  table = aggregate_champ_table(bucket_matches, puuid)

  top3_fmt = [_champ_row_out(r) for r in _top3(table)]
  overall_fmt = _overall_out(overall)
  best_fmt = _champ_row_out(best)
  standout = pick_standout_metric_overall(overall)
  fun_stat = fun_stat_from_matches(bucket_matches, puuid)

  if standout and isinstance(standout.get("value"), str):
    try:
      standout["value"] = f"{float(standout['value']):.2f}"
    except Exception:
      pass

  return {
    "splitId": split_id,
    "patchRange": patch_range,
    "gamesAnalyzed": len(bucket_matches),
    "primaryQueue": primary_bucket,
    "overall": overall_fmt,
    "bestChamp": best_fmt,
    "standout": standout,
    "topChamps": top3_fmt,
    "funStat": fun_stat,
  }

# ----------------------------
# Year summary endpoint (single fetch → fan out)
# ----------------------------
@router.get("/year-summary")
async def year_summary(
    region: Optional[str] = None,
    riotId: str = "",
    includeFeelGood: bool = True,
    includeAdvice: bool = True,
):
  """
  GET /api/year-summary?riotId=MK1Paris%23NA1[&includeFeelGood=true][&includeAdvice=true]
  Optional region: americas|europe|asia|sea (auto-detected if omitted)
  """
  if "#" not in riotId and "%23" not in riotId:
    raise HTTPException(400, "riotId must be Name#TAG (e.g., MK1Paris#NA1)")
  name, tag = riotId.replace("%23", "#").split("#", 1)

  # 1) Resolve regional cluster
  reg = (region or "").strip().lower()
  if reg not in ("americas", "europe", "asia", "sea"):
    reg = await _resolve_region_for_riot_id(name, tag)
    if not reg:
      raise HTTPException(404, "Could not resolve regional cluster for this Riot ID.")

  # 2) Resolve PUUID + parallelize platform + matches
  puuid = await _cached_puuid(reg, name, tag)
  matches_task = asyncio.create_task(_cached_all_matches(reg, puuid))
  platform_task = asyncio.create_task(_derive_platform_from_activity(reg, puuid))
  all_matches, platform = await asyncio.gather(matches_task, platform_task)

  # 3) Build splits concurrently
  split_build_tasks = [asyncio.to_thread(_build_split_block, s, all_matches, puuid) for s in SPLITS.keys()]
  split_block_list = await asyncio.gather(*split_build_tasks)
  split_blocks = { s: block for s, block in zip(SPLITS.keys(), split_block_list) }

  # 4) Year aggregation
  if not all_matches:
    resp = {
      "splits": split_blocks,
      "year": {
        "primaryQueue": "unranked",
        "gamesAnalyzed": 0,
        "overall": None,
        "bestChamp": None,
        "topChamps": [],
        "standout": None,
        "funStat": None,
        "feelGood": None,
        "advice": None,
      }
    }
    if platform:
      resp["currentRank"] = await _cached_current_rank(platform, puuid)
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
  best_y = aggregate_best_champ(bucket_matches_y, puuid)
  table_y = aggregate_champ_table(bucket_matches_y, puuid)

  best_y_fmt = _champ_row_out(best_y)
  top3_y_fmt = [_champ_row_out(r) for r in _top3(table_y)]
  standout_y = pick_standout_metric_overall(overall_raw)
  fun_y = fun_stat_from_matches(bucket_matches_y, puuid)

  # Optional LLM bits
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
      "overall": overall_raw,          # raw numbers (LLM can see floats)
      "bestChamp": best_y,             # raw row
      "topChamps": table_y[:3],        # raw top3
      "standout": standout_y,
      "funStat": fun_y,                # include so LLM can turn it into a punchy 'fun' line
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
      "standout": standout_y,
      "funStat": fun_y,       # numeric/generic record
      "feelGood": feel_good,  # short hype line
      "advice": advice,       # summary/insights/focus/fun (punchy)
    }
  }
  if platform:
    resp["currentRank"] = await _cached_current_rank(platform, puuid)
  return resp
