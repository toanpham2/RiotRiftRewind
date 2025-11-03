from collections import Counter, defaultdict
from math import exp
from typing import Dict, List, Tuple, Optional
import asyncio
import math
import re

from app.config import SPLITS
from app.riot_client import RiotClient

# ----------------------------
# Queue & role maps
# ----------------------------
QUEUE_BUCKET = {
  420: "solo",
  440: "flex",
  400: "normal",
  430: "normal",
  450: "aram",
  700: "clash",
}

ROLE_MAP = {
  "TOP": "top",
  "JUNGLE": "jungle",
  "MIDDLE": "mid",
  "BOTTOM": "adc",
  "UTILITY": "support",
}

# ----------------------------
# Scoring tunables
# ----------------------------
VOLUME_BONUS_LAMBDA = 25.0
VOLUME_BONUS_CAP = 0.50
MIN_GAMES_FOR_BEST = 15

# ----------------------------
# Helpers
# ----------------------------
def _wilson_lower_bound(p: float, n: int, z: float = 1.281551565545) -> float:  # ~80% CI
  if n == 0:
    return 0.0
  denom = 1.0 + z * z / n
  center = p + z * z / (2 * n)
  margin = z * math.sqrt((p * (1 - p) / n) + (z * z / (4 * n * n)))
  return (center - margin) / denom

def _cap(x: float, hi: float) -> float:
  return min(max(x, 0.0), hi)

def _norm(x: float, target: float, cap_hi: float) -> float:
  if target <= 1e-9:
    return 0.0
  return _cap(x / target, cap_hi)

def _role_weights(role: str) -> Dict[str, float]:
  role = (role or "unknown").lower()
  if role in ("top", "mid", "adc"):
    return {"wr": 1.0, "kda": 0.6, "cs": 0.7, "kp": 0.4, "vision": 0.2, "dmgshare": 0.8}
  if role == "jungle":
    return {"wr": 1.0, "kda": 0.6, "cs": 0.4, "kp": 0.8, "vision": 0.3, "dmgshare": 0.5}
  if role == "support":
    return {"wr": 0.9, "kda": 0.5, "cs": 0.0, "kp": 0.8, "vision": 1.0, "dmgshare": 0.2}
  return {"wr": 1.0, "kda": 0.5, "cs": 0.4, "kp": 0.6, "vision": 0.3, "dmgshare": 0.5}

def _per_match_team_totals(info: dict, team_id: int) -> Tuple[int, int]:
  team_kills = 0
  team_dmg = 0
  for p in info.get("participants", []):
    if p.get("teamId") == team_id:
      team_kills += p.get("kills", 0)
      team_dmg += p.get("totalDamageDealtToChampions", 0)
  return team_kills, team_dmg

def _pct(x: float) -> str:
  """Convert a fraction (0.5536) → '55.36%'."""
  return f"{x*100:.2f}%"

def patch_tuple(game_version: str) -> Tuple[int, int]:
  """Extract first two integers from version string (robust)."""
  nums = re.findall(r"\d+", game_version or "")
  if len(nums) >= 2:
    return int(nums[0]), int(nums[1])
  return (0, 0)

def within_patch_range(game_version: str, lo: str, hi: str) -> bool:
  g = patch_tuple(game_version)
  L = patch_tuple(lo)
  H = patch_tuple(hi)
  return L <= g <= H

def filter_matches_by_split(matches: List[dict], split: str) -> List[dict]:
  lo, hi = SPLITS.get(split, SPLITS["s1"])
  out = []
  for m in matches:
    gv = m.get("info", {}).get("gameVersion", "")
    if within_patch_range(gv, lo, hi):
      out.append(m)
  return out

def classify_primary_mode(matches: List[dict]) -> Dict:
  if not matches:
    return {"primary": "unranked", "confidence": 0.0, "dist": {}}

  weighted = Counter()
  base = Counter()
  for i, m in enumerate(matches):
    qid = m.get("info", {}).get("queueId")
    bucket = QUEUE_BUCKET.get(qid)
    if not bucket:
      continue
    w = exp(-i / 20.0)
    weighted[bucket] += w
    base[bucket] += 1

  if not weighted:
    return {"primary": "unranked", "confidence": 0.0, "dist": {}}

  items = sorted(weighted.items(), key=lambda kv: kv[1], reverse=True)
  top, top_w = items[0]
  second_w = items[1][1] if len(items) > 1 else 0.0
  total_w = sum(weighted.values())
  margin = (top_w - second_w) / max(1e-6, total_w)
  confidence = max(0.0, min(1.0, margin * 2.0))

  ranked_games = base["solo"] + base["flex"]
  if ranked_games < 5 and base["normal"] >= 5:
    top, confidence = "normal", max(confidence, 0.6)

  return {
    "primary": top,
    "confidence": round(confidence, 2),
    "dist": {k: int(v) for k, v in base.items()},
  }

# ----------------------------
# Per-split champion selection
# ----------------------------
def aggregate_best_champ(matches: List[dict], puuid: str) -> Optional[dict]:
  if not matches:
    return None

  per = defaultdict(lambda: {
    "games": 0, "wins": 0,
    "k": 0, "d": 0, "a": 0,
    "time": 0, "cs": 0, "vision": 0,
    "kp_sum": 0.0, "dmg_share_sum": 0.0,
    "role": "unknown",
  })

  for m in matches:
    info = m.get("info", {})
    parts = info.get("participants", [])
    you = next((p for p in parts if p.get("puuid") == puuid), None)
    if not you:
      continue

    champ = you.get("championName", "Unknown")
    role = ROLE_MAP.get(you.get("teamPosition", ""), "unknown")
    team_id = you.get("teamId")

    team_kills, team_dmg = _per_match_team_totals(info, team_id)
    kp_match = (you.get("kills", 0) + you.get("assists", 0)) / team_kills if team_kills > 0 else 0.0
    dmg_share_match = you.get("totalDamageDealtToChampions", 0) / team_dmg if team_dmg > 0 else 0.0

    r = per[champ]
    r["games"] += 1
    r["wins"] += 1 if you.get("win") else 0
    r["k"] += you.get("kills", 0)
    r["d"] += you.get("deaths", 0)
    r["a"] += you.get("assists", 0)
    r["time"] += you.get("timePlayed", info.get("gameDuration", 0))
    r["cs"] += you.get("totalMinionsKilled", 0) + you.get("neutralMinionsKilled", 0)
    r["vision"] += you.get("visionScore", 0)
    r["kp_sum"] += kp_match
    r["dmg_share_sum"] += dmg_share_match
    r["role"] = role or r["role"]

  if not per:
    return None

  total_games = sum(r["games"] for r in per.values())

  best_row = None
  best_score = -1.0

  for champ, r in per.items():
    n = r["games"]
    if n < MIN_GAMES_FOR_BEST:
      continue
    wins = r["wins"]
    wr = wins / max(1, n)

    time_min = max(1, r["time"] / 60)
    kda = (r["k"] + r["a"]) / max(1, r["d"])
    cs_min = r["cs"] / time_min
    vision_min = r["vision"] / time_min
    kp = r["kp_sum"] / max(1, n)
    dmg_share = r["dmg_share_sum"] / max(1, n)
    role = r["role"]

    wr_adj = _wilson_lower_bound(wr, n, z=1.96)

    kda_n = _norm(kda, 4.0, 1.2)
    cs_n  = _norm(cs_min, 7.0, 1.2)
    kp_n  = _norm(kp, 0.60, 1.2)
    vis_n = _norm(vision_min, 1.0, 1.3)
    dmg_n = _norm(dmg_share, 0.25, 1.4)

    w = _role_weights(role)
    score = (
        60 * wr_adj
        + 20.0 * (w["kda"] * kda_n + w["cs"] * cs_n + w["kp"] * kp_n + w["vision"] * vis_n + w["dmgshare"] * dmg_n)
    )

    stability = ( math.log1p(n) / math.log1p(40) ) * min(1.0, n / 20.0)
    score *= stability

    if total_games > 0:
      share = min(n / total_games, VOLUME_BONUS_CAP)
      score += VOLUME_BONUS_LAMBDA * share

    if score > best_score:
      best_score = score
      best_row = {
        "name": champ,
        "role": role,
        "games": n,
        "winrate": _pct(wr),
        "kda": round(kda, 2),
        "csPerMin": round(cs_min, 2),
        "visionPerMin": round(vision_min, 2),
        "kp": _pct(kp),
        "dmgShare": _pct(dmg_share),
        "score": round(score, 2),
      }

  return best_row

def aggregate_overall_metrics(matches: List[dict], puuid: str) -> Optional[dict]:
  if not matches:
    return None

  total = {"games": 0, "wins": 0, "k": 0, "d": 0, "a": 0, "time": 0, "cs": 0, "vision": 0}
  role_counts = Counter()

  for m in matches:
    info = m.get("info", {})
    you = next((p for p in info.get("participants", []) if p.get("puuid") == puuid), None)
    if not you:
      continue
    total["games"] += 1
    total["wins"] += 1 if you.get("win") else 0
    total["k"] += you.get("kills", 0)
    total["d"] += you.get("deaths", 0)
    total["a"] += you.get("assists", 0)
    total["time"] += you.get("timePlayed", info.get("gameDuration", 0))
    total["cs"] += you.get("totalMinionsKilled", 0) + you.get("neutralMinionsKilled", 0)
    total["vision"] += you.get("visionScore", 0)
    role_counts[ROLE_MAP.get(you.get("teamPosition", ""), "unknown")] += 1

  if total["games"] == 0:
    return None

  time_min = max(1, total["time"] / 60)
  primary_role = role_counts.most_common(1)[0][0] if role_counts else "unknown"

  return {
    "games": total["games"],
    "winrate": _pct(total["wins"] / total["games"]),
    "kda": round((total["k"] + total["a"]) / max(1, total["d"]), 2),
    "csPerMin": round(total["cs"] / time_min, 2),
    "visionPerMin": round(total["vision"] / time_min, 2),
    "primaryRole": primary_role,
  }

def aggregate_champ_table(matches: List[dict], puuid: str) -> List[dict]:
  if not matches:
    return []

  per = defaultdict(lambda: {
    "games": 0, "wins": 0,
    "k": 0, "d": 0, "a": 0,
    "time": 0, "cs": 0, "vision": 0,
    "kp_sum": 0.0, "dmg_share_sum": 0.0,
    "role": "unknown",
  })

  for m in matches:
    info = m.get("info", {})
    parts = info.get("participants", [])
    you = next((p for p in parts if p.get("puuid") == puuid), None)
    if not you:
      continue

    champ = you.get("championName", "Unknown")
    role = ROLE_MAP.get(you.get("teamPosition", ""), "unknown")
    team_id = you.get("teamId")

    team_kills, team_dmg = _per_match_team_totals(info, team_id)
    kp_match = (you.get("kills", 0) + you.get("assists", 0)) / team_kills if team_kills > 0 else 0.0
    dmg_share_match = you.get("totalDamageDealtToChampions", 0) / team_dmg if team_dmg > 0 else 0.0

    r = per[champ]
    r["games"] += 1
    r["wins"] += 1 if you.get("win") else 0
    r["k"] += you.get("kills", 0)
    r["d"] += you.get("deaths", 0)
    r["a"] += you.get("assists", 0)
    r["time"] += you.get("timePlayed", info.get("gameDuration", 0))
    r["cs"] += you.get("totalMinionsKilled", 0) + you.get("neutralMinionsKilled", 0)
    r["vision"] += you.get("visionScore", 0)
    r["kp_sum"] += kp_match
    r["dmg_share_sum"] += dmg_share_match
    r["role"] = role or r["role"]

  rows: List[dict] = []
  total_games = sum(r["games"] for r in per.values())

  for champ, r in per.items():
    n = r["games"]
    wins = r["wins"]
    wr = wins / max(1, n)

    time_min = max(1, r["time"] / 60)
    kda = (r["k"] + r["a"]) / max(1, r["d"])
    cs_min = r["cs"] / time_min
    vision_min = r["vision"] / time_min
    kp = r["kp_sum"] / max(1, n)
    dmg_share = r["dmg_share_sum"] / max(1, n)
    role = r["role"]

    wr_adj = _wilson_lower_bound(wr, n, z=1.2816)

    kda_n = _norm(kda, 4.0, 1.2)
    cs_n  = _norm(cs_min, 7.0, 1.2)
    kp_n  = _norm(kp, 0.60, 1.2)
    vis_n = _norm(vision_min, 1.0, 1.3)
    dmg_n = _norm(dmg_share, 0.25, 1.4)

    w = _role_weights(role)
    score = (
        100.0 * wr_adj
        + 20.0 * (w["kda"] * kda_n + w["cs"] * cs_n + w["kp"] * kp_n + w["vision"] * vis_n + w["dmgshare"] * dmg_n)
    )
    score *= min(1.0, n / 5.0)

    if total_games > 0:
      share = min(n / total_games, VOLUME_BONUS_CAP)
      score += VOLUME_BONUS_LAMBDA * share

    rows.append({
      "name": champ,
      "role": role,
      "games": n,
      "wins": wins,
      "winrate": _pct(wr),
      "kda": round(kda, 2),
      "csPerMin": round(cs_min, 2),
      "visionPerMin": round(vision_min, 2),
      "kp": _pct(kp),
      "dmgShare": _pct(dmg_share),
      "score": round(score, 2),
    })

  rows.sort(key=lambda r: r["score"], reverse=True)
  return rows

def pick_standout_metric_overall(overall: Optional[dict]) -> Optional[dict]:
  if not overall:
    return None
  role = overall.get("primaryRole", "unknown")
  if role == "support":
    return {
      "label": "Vision / min",
      "value": f"{overall['visionPerMin']:.2f}",
      "context": "overall",
      "background": {"kind": "icon", "ref": "vision"},
    }
  if role == "jungle":
    return {
      "label": "Farm / min",
      "value": f"{overall['csPerMin']:.2f}",
      "context": "overall",
      "background": {"kind": "icon", "ref": "jungle"},
    }
  return {
    "label": "CS / min",
    "value": f"{overall['csPerMin']:.2f}",
    "context": "overall",
    "background": {"kind": "icon", "ref": "cs"},
  }

# ----------------------------
# Fetching
# ----------------------------
async def fetch_matches_for_split(region: str, puuid: str, split: str,
    *, max_batches: int = 120, batch_size: int = 100) -> List[dict]:
  if split not in SPLITS:
    return []
  lo, hi = SPLITS[split]
  lo_t = patch_tuple(lo)
  collected: List[dict] = []
  start = 0

  async with RiotClient() as rc:
    for _ in range(max_batches):
      ids = await rc.match_ids(region, puuid, start=start, count=batch_size)
      if not ids:
        break

      results = await asyncio.gather(
          *[rc.match(region, mid) for mid in ids],
          return_exceptions=True
      )

      oldest_this_page = None
      for m in results:
        if isinstance(m, Exception):
          continue
        info = m.get("info", {})
        gv = info.get("gameVersion", "")
        g_t = patch_tuple(gv)

        if within_patch_range(gv, lo, hi):
          collected.append(m)

        if g_t != (0, 0):
          if not oldest_this_page or g_t < oldest_this_page:
            oldest_this_page = g_t

      if oldest_this_page and oldest_this_page < lo_t:
        break

      start += batch_size

  return collected

async def fetch_matches_since_patch(region: str, puuid: str, lo_patch: str,
    *, max_batches: int = 180, batch_size: int = 100) -> List[dict]:
  """
  Fetch all matches from the given lower-bound patch (inclusive) upward.
  Stops paging once a page contains matches older than lo_patch.
  """
  lo_t = patch_tuple(lo_patch)
  collected: List[dict] = []
  start = 0

  async with RiotClient() as rc:
    for _ in range(max_batches):
      ids = await rc.match_ids(region, puuid, start=start, count=batch_size)
      if not ids:
        break

      results = await asyncio.gather(
          *[rc.match(region, mid) for mid in ids],
          return_exceptions=True
      )

      oldest_this_page = None
      for m in results:
        if isinstance(m, Exception):
          continue
        info = m.get("info", {})
        gv = info.get("gameVersion", "")
        g_t = patch_tuple(gv)

        # Keep everything >= lo_patch; no upper bound.
        if g_t >= lo_t:
          collected.append(m)

        if g_t != (0, 0):
          if not oldest_this_page or g_t < oldest_this_page:
            oldest_this_page = g_t

      if oldest_this_page and oldest_this_page < lo_t:
        break

      start += batch_size

  return collected

def filter_matches_by_bucket(matches: List[dict], bucket: str) -> List[dict]:
  out = []
  for m in matches:
    qid = m.get("info", {}).get("queueId")
    if QUEUE_BUCKET.get(qid) == bucket:
      out.append(m)
  return out

def fun_stat_from_matches(matches: List[dict], puuid: str) -> Optional[dict]:
  """Example simple 'oops' stat: highest deaths game."""
  worst = None
  for m in matches:
    info = m.get("info", {})
    you = next((p for p in info.get("participants", []) if p.get("puuid") == puuid), None)
    if not you:
      continue
    deaths = you.get("deaths", 0)
    if worst is None or deaths > worst["deaths"]:
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
