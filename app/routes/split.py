from fastapi import APIRouter, HTTPException
from typing import Optional, Dict, Any
import json

from app.riot_client import RiotClient
from app.config import SPLITS
from app.services.split_agg import (
  fetch_matches_for_split,   # <— deep pagination per split
  classify_primary_mode,
  aggregate_best_champ,
  pick_standout_metric,
  filter_matches_by_bucket,
)
from app.bedrock_client import coach_with_claude

router = APIRouter(prefix="/api", tags=["split"])


def _advice_payload(
    split_id: str,
    patch_range: str,
    games_analyzed: int,
    primary_queue: str,
    best: Optional[dict],
    standout: Optional[dict],
) -> Dict[str, Any]:
  """
  Keep the payload compact. Claude does better with fewer, high-signal fields.
  """
  return {
    "splitId": split_id,
    "patchRange": patch_range,
    "gamesAnalyzed": games_analyzed,
    "primaryQueue": primary_queue or "unranked",
    "bestChamp": best,       # {name, role, games, winrate, kda, csPerMin?, visionPerMin?}
    "standout": standout,    # {label, value, context, background}
  }


def _claude_split_advice(payload: dict) -> Optional[dict]:
  """
  Ask Claude for a tiny, structured summary. JSON only.
  """
  system = (
    "You are Rift Rewind, a concise League of Legends coach. "
    "Given split-level stats (one split only), return STRICT JSON with: "
    "a two-sentence summary (<= 45 words total) and exactly three actionable bullets "
    "with a measurable target. Be role-aware (support: vision; jungle: objectives; others: cs/dmg/kp). "
    "If gamesAnalyzed is small (<5), emphasize stable champ/role and sample size."
  )

  user = f"""DATA:
{json.dumps(payload, ensure_ascii=False)}

FORMAT:
{{
  "summary": "<two sentences, <=45 words total>",
  "bullets": [
    {{"action":"<what to do>","why":"<why>","target":"<measurable>"}},
    {{"action":"<what to do>","why":"<why>","target":"<measurable>"}},
    {{"action":"<what to do>","why":"<why>","target":"<measurable>"}}
  ]
}}
Rules:
- JSON only, no markdown.
- If bestChamp is null, avoid inventing a champ; give general, role-agnostic improvement targets.
- Targets must be measurable (e.g., 'CS/min ≥ 6.5 over next 10 games', 'Vision/min ≥ 1.0', 'Deaths/game ≤ 4')."""

  try:
    raw = coach_with_claude(system, user, max_tokens=600, temperature=0.4)
    # guard against non-JSON replies
    return json.loads(raw)
  except Exception:
    # fallback (don’t break the endpoint if Bedrock has a hiccup)
    return {
      "summary": "Unable to fetch AI advice right now. Your split stats are below.",
      "bullets": [
        {"action": "Play consistent role", "why": "Stabilize performance for analysis", "target": "10 games same role"},
        {"action": "Focus one champion", "why": "Build mechanics & matchup depth", "target": "15+ games on one champ"},
        {"action": "Reduce deaths", "why": "Win more close games", "target": "≤4 deaths/game over next 10 games"},
      ],
    }


@router.get("/split-summary")
async def split_summary(region: str, riotId: str, split: str):
  """
  Example:
    /api/split-summary?region=americas&riotId=MK1Paris%23NA1&split=s1

  Behavior:
    - Deep-paginates history to find matches within the split's patch window.
    - Computes primary queue, best champion, standout metric.
    - Calls Claude for compact, measurable advice (JSON).
  """
  if "#" not in riotId and "%23" not in riotId:
    raise HTTPException(400, "riotId must be formatted as Name#TAG (e.g., MK1Paris#NA1)")
  name, tag = riotId.replace("%23", "#").split("#", 1)

  if split not in SPLITS:
    raise HTTPException(400, f"split must be one of {list(SPLITS.keys())}")

  lo, hi = SPLITS[split]
  patch_range = f"{lo} - {hi}"

  # Resolve player
  async with RiotClient() as rc:
    puuid = await rc.puuid_by_riot_id(region, name, tag)

  # Deep fetch just this split (the key fix so s1 isn’t empty)
  raw_matches = await fetch_matches_for_split(region, puuid, split)
  games_analyzed = len(raw_matches)

  if games_analyzed == 0:
    payload = _advice_payload(split, patch_range, 0, "unranked", None, None)
    advice = _claude_split_advice(payload)
    return {
      "splitId": split,
      "patchRange": patch_range,
      "gamesAnalyzed": 0,
      "primaryQueue": "unranked",
      "mostPlayedRankType": "unranked",
      "rankNow": None,
      "peakRank": None,
      "bestChamp": None,
      "standout": None,
      "advice": advice,
    }

  # Aggregate your metrics
  primary_info = classify_primary_mode(raw_matches)
  primary_bucket = primary_info.get("primary") or "unranked"
  # If we somehow got 'unranked' but have normals/aram etc.,
  # pick the bucket with the largest count from the dist
  if primary_bucket == "unranked":
    dist = primary_info.get("dist", {})
    if dist:
      primary_bucket = max(dist.items(), key=lambda kv: kv[1])[0]

  # Filter matches to the most-played bucket before computing "best champ"
  bucket_matches = (
    filter_matches_by_bucket(raw_matches, primary_bucket)
    if primary_bucket and primary_bucket != "unranked"
    else raw_matches
  )
  best = aggregate_best_champ(raw_matches, puuid)
  standout = pick_standout_metric(best)

  # Build advice payload & call Claude
  payload = _advice_payload(
      split_id=split,
      patch_range=patch_range,
      games_analyzed=games_analyzed,
      primary_queue=primary_info.get("primary", "unranked"),
      best=best,
      standout=standout,
  )
  advice = _claude_split_advice(payload)

  return {
    "splitId": split,
    "patchRange": patch_range,
    "gamesAnalyzed": games_analyzed,
    "primaryQueue": primary_info.get("primary", "unranked"),
    "mostPlayedRankType": primary_info.get("primary", "unranked"),
    "rankNow": None,     # (optional) wire ranked endpoints if you want live rank/peak
    "peakRank": None,
    "bestChamp": best,
    "standout": standout,
    "advice": advice,
  }
