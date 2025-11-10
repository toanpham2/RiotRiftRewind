# app/routes/matches.py
from fastapi import APIRouter, HTTPException
from app.riot_client import RiotClient
from app.config import QUEUES
from app.models import MatchesResponse, MatchBrief, YouBrief

import asyncio

router = APIRouter(prefix="/api", tags=["matches"])

@router.get("/matches", response_model=MatchesResponse)
async def get_matches(region: str, riotId: str, mode: str = "all", start: int = 0, count: int = 20):
  """
  Example:
    /api/matches?region=americas&riotId=MK1Paris#NA1&mode=solo&start=0&count=20
  """
  if "#" not in riotId:
    raise HTTPException(400, "riotId must be formatted as Name#TAG (e.g., MK1Paris#NA1)")

  game_name, tag_line = riotId.split("#", 1)
  count = max(1, min(count, 50))  # clamp for safety

  async with RiotClient() as rc:
    # 1) PUUID
    try:
      puuid = await rc.puuid_by_riot_id(region, game_name, tag_line)
    except Exception as e:
      raise HTTPException(400, f"Account lookup failed: {e}")

    # 2) Match IDs (+ queue filter if single queue)
    queues = None if mode.lower() == "all" else QUEUES.get(mode.lower())

    ids: list[str] = []
    try:
      if queues and len(queues) == 1:
        ids = await rc.match_ids(region, puuid, start=start, count=count, queue=queues[0])
      else:
        # multi-queue or all: overfetch some IDs, then lazily fetch details until we have 'count'
        # this avoids touching hundreds of matches unnecessarily
        overfetch = max(count * 3, 60)          # up to 3x the target
        raw = await rc.match_ids(region, puuid, start=start, count=overfetch)
        if queues:
          targets = set(queues)
          sem = asyncio.Semaphore(6)            # bounded detail calls

          async def _ok(mid: str) -> bool:
            async with sem:
              m = await rc.match(region, mid)
              q = m.get("info", {}).get("queueId", -1)
              return q in targets

          ok_flags = await asyncio.gather(*[_ok(mid) for mid in raw])
          ids = [mid for mid, ok in zip(raw, ok_flags) if ok][:count]
        else:
          ids = raw[:count]
    except Exception as e:
      raise HTTPException(400, f"Match ID lookup failed: {e}")

    # 3) Brief list (bounded concurrency)
    sem = asyncio.Semaphore(8)

    async def _brief(mid: str) -> MatchBrief:
      async with sem:
        m = await rc.match(region, mid)
        info = m.get("info", {})
        gv = info.get("gameVersion", "")
        patch = ""
        try:
          major, minor, *_ = gv.split(".")
          patch = f"{int(major)}.{int(minor)}"
        except Exception:
          patch = ""
        you = next((p for p in info.get("participants", []) if p.get("puuid") == puuid), None)
        youb = YouBrief(
            champion=you.get("championName", "") if you else "",
            kills=you.get("kills", 0) if you else 0,
            deaths=you.get("deaths", 0) if you else 0,
            assists=you.get("assists", 0) if you else 0,
            win=bool(you.get("win")) if you else False,
        )
        return MatchBrief(
            matchId=mid,
            queueId=info.get("queueId", -1),
            gameMode=info.get("gameMode", ""),
            durationSec=info.get("gameDuration", you.get("timePlayed", 0) if you else 0),
            patch=patch,
            you=youb
        )

    briefs = await asyncio.gather(*[_brief(mid) for mid in ids])
    nextStart = start + len(ids)
    return MatchesResponse(region=region, riotId=riotId, puuid=puuid,
                           mode=mode, start=start, nextStart=nextStart, matches=briefs)
