from app.config import SPLITS
import json
from typing import Optional, Literal, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import SPLITS
from app.riot_client import RiotClient
from app.services.split_agg import (
  filter_matches_by_split,
  classify_primary_mode,
  aggregate_best_champ,
  pick_standout_metric,
)
from app.bedrock_client import coach_with_claude

router = APIRouter(prefix="/api", tags=["split"])

# ---------- Response models ----------
class Rank(BaseModel):
  tier: str
  division: Optional[str] = None
  lp: Optional[int] = None

class AdviceBullet(BaseModel):
  action: str
  why: str
  target: str

class SplitAdvice(BaseModel):
  summary: str
  bullets: List[AdviceBullet]

class SplitSummary(BaseModel):
  splitId: str
  patchRange: str
  gamesAnalyzed: int
  primaryQueue: Literal["solo", "flex", "normal", "aram", "clash", "unranked"]
  mostPlayedRankType: Literal["solo", "flex", "unranked"]
  rankNow: Optional[Rank] = None      # optional for hackathon
  peakRank: Optional[Rank] = None     # optional for hackathon
  bestChamp: Optional[dict] = None
  standout: Optional[dict] = None
  advice: Optional[SplitAdvice] = None

# ---------- Helpers for Claude ----------
def _build_advice_payload(splitId: str, patchRange: str, primary: str, best: Optional[dict], standout: Optional[dict]) -> dict:
  return {
    "splitId": splitId,
    "patchRange": patchRange,
    "primaryMode": primary,
    "bestChamp": best,
    "standout": standout,
  }

def _advice_from_claude(payload: dict) -> Optional[SplitAdvice]:
  system = (
    "You are Rift Rewind, a concise League coach. "
    "Given split stats, write a two-sentence summary (strengths + one weakness) "
    "and EXACTLY three actionable bullets with measurable targets. Output strict JSON only."
  )
  user = f"""SPLIT_DATA:
{json.dumps(payload, ensure_ascii=False)}

FORMAT:
{{
  "summary":"<two sentences, <=45 words total>",
  "bullets":[
    {{"action":"<what to do>","why":"<why>","target":"<measurable>"}},
    {{"action":"<what to do>","why":"<why>","target":"<measurable>"}},
    {{"action":"<what to do>","why":"<why>","target":"<measurable>"}}
  ]
}}
Rules:
- Be role-aware: support -> vision; jungle -> objectives; others -> cs/dmg/kp/laning.
- No markdown. No extra keys. JSON only."""
  try:
    raw = coach_with_claude(system, user, max_tokens=500, temperature=0.4)
    data = json.loads(raw)
    bullets: List[AdviceBullet] = []
    for b in (data.get("bullets") or [])[:3]:
      if all(k in b for k in ("action", "why", "target")):
        bullets.append(AdviceBullet(**b))
    if "summary" in data and len(bullets) == 3:
      return SplitAdvice(summary=data["summary"], bullets=bullets)
  except Exception:
    return None
  return None

# ---------- Endpoint ----------
@router.get("/split-summary", response_model=SplitSummary)
async def split_summary(region: str, riotId: str, split: str = "s1", withAdvice: bool = True):
  """
  Example:
    /api/split-summary?region=americas&riotId=MK1Paris%23NA1&split=s1
  Accepts split in {"s1","s2","s3"} per Season 15.
  """
  if "#" not in riotId and "%23" not in riotId:
    raise HTTPException(400, "riotId must be formatted as Name#TAG (e.g., MK1Paris#NA1)")
  if split not in SPLITS:
    raise HTTPException(400, f"split must be one of {list(SPLITS.keys())}")

  name, tag = riotId.replace("%23", "#").split("#", 1)

  # 1) Pull matches (cap count for perf; bump if you need more history)
  async with RiotClient() as rc:
    puuid = await rc.puuid_by_riot_id(region, name, tag)
    ids = await rc.match_ids(region, puuid, start=0, count=50)
    raw_matches = [await rc.match(region, mid) for mid in ids]

  # 2) Filter by split patch window
  lo, hi = SPLITS[split]
  split_matches = filter_matches_by_split(raw_matches, split)
  patch_range = f"{lo} - {hi}"

  # 3) Primary queue detection + “mostPlayedRankType”
  mode_info = classify_primary_mode(split_matches)
  primary_queue = mode_info["primary"]
  # best-effort for “mostPlayedRankType”
  solo_ct = mode_info["dist"].get("solo", 0)
  flex_ct = mode_info["dist"].get("flex", 0)
  if solo_ct == 0 and flex_ct == 0:
    most_rank = "unranked"
  else:
    most_rank = "solo" if solo_ct >= flex_ct else "flex"

  # 4) Best champ & role-aware standout
  best = aggregate_best_champ(split_matches, puuid)
  standout = pick_standout_metric(best)

  # 5) (Optional) rankNow / peakRank (stubbed)
  rank_now = None
  peak_rank = None

  # 6) Pack response
  result = SplitSummary(
      splitId=split,
      patchRange=patch_range,
      gamesAnalyzed=len(split_matches),
      primaryQueue=primary_queue,
      mostPlayedRankType=most_rank,
      rankNow=rank_now,
      peakRank=peak_rank,
      bestChamp=best,
      standout=standout,
      advice=None,
  )

  # 7) Claude advice (optional)
  if withAdvice:
    payload = _build_advice_payload(split, patch_range, primary_queue, best, standout)
    result.advice = _advice_from_claude(payload)

  return result