from app.config import SPLITS

from collections import Counter, defaultdict
from math import exp
from typing import Dict, List, Tuple, Optional
import asyncio
from app.config import SPLITS
from app.riot_client import RiotClient

QUEUE_BUCKET ={
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

def patch_tuple(game_version: str) -> Tuple[int, int]:
  """14.13.512.1234" -> (14, 13)"""
  try:
    major, minor, *_ = (game_version or "").split(".")
    return int(major), int(minor)
  except Exception:
    return (0, 0)

def within_patch_range(game_version: str, lo: str, hi: str) -> bool:
  g = patch_tuple(game_version)
  L = patch_tuple(lo)
  H = patch_tuple(hi)
  return L <= g <= H

def filter_matches_by_split(matches: List[dict], split: str) -> List[dict]:
  lo, hi = SPLITS.get(split, SPLITS["s1"])
  out = []
  for m in matches :
    gv = m.get("info", {}).get("gameVersion","")
    if within_patch_range(gv, lo, hi):
      out.append(m)
  return out

def classify_primary_mode(matches: List[dict]) -> Dict:
  if not matches:
    return {"primary": "unranked", "confidence": 0.0, "dist": {}}

  weighted = Counter()
  base = Counter()
  for i, m in enumerate(matches):
    qid = m.get("info",{}).get("queueId")
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

  # Prefer normals if ranked volume is tiny
  ranked_games = base["solo"] + base["flex"]
  if ranked_games < 5 and base["normal"] >= 5:
    top, confidence = "normal", max(confidence, 0.6)

  return {
    "primary": top,
    "confidence": round(confidence, 2),
    "dist": {k: int(v) for k, v in base.items()},
  }


def aggregate_best_champ(matches: List[dict], puuid: str) -> Optional[dict]:
  """
  Roll up by champion; choose best by WR (min 3 games) then KDA.
  Returns:
    {
      "name": str, "role": str, "games": int,
      "winrate": float, "kda": float,
      "csPerMin": Optional[float], "visionPerMin": Optional[float]
    }
  """
  agg = defaultdict(lambda: {
    "games": 0, "wins": 0, "k": 0, "d": 0, "a": 0,
    "time": 0, "cs": 0, "vision": 0, "role": "unknown"
  })
  for m in matches:
    info = m.get("info", {})
    you = next((p for p in info.get("participants", []) if p.get("puuid") == puuid), None)
    if not you:
      continue
    champ = you.get("championName", "Unknown")
    r = agg[champ]
    r["games"] += 1
    r["wins"] += 1 if you.get("win") else 0
    r["k"] += you.get("kills", 0)
    r["d"] += you.get("deaths", 0)
    r["a"] += you.get("assists", 0)
    r["time"] += you.get("timePlayed", info.get("gameDuration", 0))
    r["cs"] += you.get("totalMinionsKilled", 0) + you.get("neutralMinionsKilled", 0)
    r["vision"] += you.get("visionScore", 0)
    r["role"] = ROLE_MAP.get(you.get("teamPosition", ""), "unknown")

  if not agg:
    return None

  best_key = None
  best_score = -1.0
  for champ, r in agg.items():
    if r["games"] < 3:
      continue
    wr = r["wins"] / r["games"]
    kda = (r["k"] + r["a"]) / max(1, r["d"])
    score = wr * 100 + kda
    if score > best_score:
      best_score = score
      best_key = champ

  target = best_key or max(agg.keys(), key=lambda c: agg[c]["games"])
  r = agg[target]
  time_min = max(1, r["time"] / 60)
  role = r["role"]

  return {
    "name": target,
    "role": role,
    "games": r["games"],
    "winrate": r["wins"] / max(1, r["games"]),
    "kda": (r["k"] + r["a"]) / max(1, r["d"]),
    "csPerMin": (r["cs"] / time_min) if role != "support" else None,
    "visionPerMin": (r["vision"] / time_min) if role == "support" else None,
  }

def pick_standout_metric(best: Optional[dict]) -> Optional[dict]:
  """
  Pick one role-aware metric for the hero card.
  """
  if not best:
    return None
  role = best.get("role", "unknown")
  if role == "support" and best.get("visionPerMin") is not None:
    return {
      "label": "Vision Score / min",
      "value": f"{best['visionPerMin']:.2f}",
      "context": "above_average",
      "background": {"kind": "icon", "ref": "vision"},
    }
  if role == "jungle" and best.get("csPerMin") is not None:
    return {
      "label": "Farm / min",
      "value": f"{best['csPerMin']:.2f}",
      "context": "above_average",
      "background": {"kind": "icon", "ref": "jungle"},
    }
  if best.get("csPerMin") is not None:
    return {
      "label": "CS / min",
      "value": f"{best['csPerMin']:.2f}",
      "context": "above_average",
      "background": {"kind": "icon", "ref": "cs"},
    }
  return None

async def fetch_matches_for_split(
    region: str,
    puuid: str,
    split: str,
    *,
    max_batches: int = 40,     # go deep: 40 * 100 = 4000 matches
    batch_size: int = 100
) -> List[dict]:
  """
  Page through match history and return only matches inside the split's patch window.
  Details are fetched in parallel per page for speed.
  """
  if split not in SPLITS:
    return []
  lo, hi = SPLITS[split]
  collected: List[dict] = []
  start = 0

  async with RiotClient() as rc:
    for _ in range(max_batches):
      ids = await rc.match_ids(region, puuid, start=start, count=batch_size)
      if not ids:
        break

      # parallel detail fetch
      results = await asyncio.gather(
          *[rc.match(region, mid) for mid in ids],
          return_exceptions=True
      )
      for m in results:
        if isinstance(m, Exception):
          continue
        info = m.get("info", {})
        gv = info.get("gameVersion", "")
        if within_patch_range(gv, lo, hi):
          collected.append(m)

      # stop early if we already have a healthy sample
      if len(collected) >= 50:
        break

      start += batch_size

  return collected


def filter_matches_by_bucket(matches: List[dict], bucket: str) -> List[dict]:
  """
  Keep only matches whose queueId maps to the requested bucket
  (e.g., 'solo', 'flex', 'normal', 'aram', 'clash').
  """
  out = []
  for m in matches:
    qid = m.get("info", {}).get("queueId")
    if QUEUE_BUCKET.get(qid) == bucket:
      out.append(m)
  return out
