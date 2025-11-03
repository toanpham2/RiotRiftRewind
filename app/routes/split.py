from fastapi import APIRouter, HTTPException
from typing import Optional, Dict, Any, List
import json

from app.riot_client import RiotClient
from app.config import SPLITS
from app.services.split_agg import (
  fetch_matches_for_split,
  classify_primary_mode,
  aggregate_best_champ,
  aggregate_champ_table,
  aggregate_overall_metrics,
  pick_standout_metric_overall,
  filter_matches_by_bucket,
  fun_stat_from_matches,
)
from app.bedrock_client import coach_with_claude

router = APIRouter(prefix="/api", tags=["split"])

def _advice_payload(
    split_id: str,
    patch_range: str,
    games_analyzed: int,
    primary_queue: str,
    overall: Optional[dict],
    best: Optional[dict],
    standout: Optional[dict],
    top_champs: List[dict],
    fun_stat: Optional[dict],
) -> Dict[str, Any]:
  return {
    "splitId": split_id,
    "patchRange": patch_range,
    "gamesAnalyzed": games_analyzed,
    "primaryQueue": primary_queue or "unranked",
    "overall": overall,
    "bestChamp": best,
    "standout": standout,
    "topChamps": top_champs,
    "funStat": fun_stat,
  }

def _claude_split_advice(payload: dict) -> dict:
  # Force “Split” terminology in the summary.
  system = (
    "You are Rift Rewind, a precise League of Legends split analyst.\n"
    "Input is structured stats for ONE split (primary queue only).\n"
    "Return STRICT JSON with keys: summary, insights, focus, fun.\n"
    "- summary: <= 45 words across 2 sentences and MUST refer to the period as a 'Split' (never 'Season').\n"
    "- insights: 3–4 concise bullets; be role-aware (support=vision; jungle=objectives/KP; lanes=CS/KDA/damage).\n"
    "- focus: 3 measurable targets (e.g., 'CS/min ≥ 6.5 over next 15 games', 'Vision ≥ 0.9/min', 'Deaths ≤ 4/game').\n"
    "- fun: one playful, light line using funStat if provided; otherwise infer something cheeky but harmless.\n"
    "If gamesAnalyzed < 5, emphasize consistency + sample size."
  )
  user = json.dumps(payload, ensure_ascii=False)

  try:
    raw = coach_with_claude(system, user, max_tokens=700, temperature=0.4)
    return json.loads(raw)
  except Exception:
    return {
      "summary": "Small sample—focus on consistency in role and champion for this split.",
      "insights": [
        "Primary queue identified; stabilize champion pool.",
        "Raise CS/vision to lane-appropriate baselines.",
        "Control deaths in mid game skirmishes."
      ],
      "focus": [
        "Play 10 games in one role",
        "Lock 1–2 champions for 15 games",
        "≤4 deaths/game across next 10 games"
      ],
      "fun": "Queue up, drink water, place wards 🧃."
    }

@router.get("/split-summary")
async def split_summary(region: str, riotId: str, split: str):
  """
  Example:
    /api/split-summary?region=americas&riotId=MK1Paris%23NA1&split=s2
  """
  if "#" not in riotId and "%23" not in riotId:
    raise HTTPException(400, "riotId must be formatted as Name#TAG (e.g., MK1Paris#NA1)")
  name, tag = riotId.replace("%23", "#").split("#", 1)

  if split not in SPLITS:
    raise HTTPException(400, f"split must be one of {list(SPLITS.keys())}")

  lo, hi = SPLITS[split]
  patch_range = f"{lo} - {hi}"

  # Resolve player PUUID
  async with RiotClient() as rc:
    puuid = await rc.puuid_by_riot_id(region, name, tag)

  # Deep fetch matches for just this split
  raw_matches = await fetch_matches_for_split(region, puuid, split)

  if not raw_matches:
    payload = _advice_payload(
        split_id=split,
        patch_range=patch_range,
        games_analyzed=0,
        primary_queue="unranked",
        overall=None,
        best=None,
        standout=None,
        top_champs=[],
        fun_stat=None,
    )
    advice = _claude_split_advice(payload)
    return {
      "splitId": split,
      "patchRange": patch_range,
      "gamesAnalyzed": 0,
      "primaryQueue": "unranked",
      "mostPlayedRankType": "unranked",
      "overall": None,
      "bestChamp": None,
      "standout": None,
      "topChamps": [],
      "funStat": None,
      "advice": advice,
    }

  # Determine primary queue INSIDE this split
  primary_info = classify_primary_mode(raw_matches)
  queue_dist = primary_info.get("dist", {})
  primary_bucket = primary_info.get("primary") or (
    max(queue_dist.items(), key=lambda kv: kv[1])[0] if queue_dist else "unranked"
  )

  # Filter to most-played bucket for all downstream stats
  bucket_matches = (
    filter_matches_by_bucket(raw_matches, primary_bucket)
    if primary_bucket and primary_bucket != "unranked"
    else raw_matches
  )

  # Compute metrics on the bucket sample
  overall = aggregate_overall_metrics(bucket_matches, puuid)
  best = aggregate_best_champ(bucket_matches, puuid)
  champs_full = aggregate_champ_table(bucket_matches, puuid)
  champs = champs_full[:3]  # ⬅️ only top 3
  standout = pick_standout_metric_overall(overall)
  fun_stat = fun_stat_from_matches(bucket_matches, puuid)

  games_analyzed = len(bucket_matches)

  # Build advice payload & call Claude (narrative only)
  payload = _advice_payload(
      split_id=split,
      patch_range=patch_range,
      games_analyzed=games_analyzed,
      primary_queue=primary_bucket,
      overall=overall,
      best=best,
      standout=standout,
      top_champs=champs,
      fun_stat=fun_stat,
  )
  advice = _claude_split_advice(payload)

  return {
    "splitId": split,
    "patchRange": patch_range,
    "gamesAnalyzed": games_analyzed,
    "primaryQueue": primary_bucket,
    "mostPlayedRankType": primary_bucket,
    "overall": overall,
    "bestChamp": best,
    "standout": standout,
    "topChamps": champs,
    "funStat": fun_stat,
    "advice": advice,
  }
