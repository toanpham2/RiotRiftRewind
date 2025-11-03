from fastapi import APIRouter, HTTPException
from app.riot_client import RiotClient
from app.config import QUEUES
from app.models import MatchesResponse, MatchBrief, YouBrief

router = APIRouter(prefix="/api", tags=["matches"])

@router.get("/matches", response_model=MatchesResponse)
async def get_matches(region: str, riotId: str, mode: str = "all", start: int = 0, count: int = 20):
  """
  Example:
    /api/matches?region=americas&riotId=MK1Paris#NA1&mode=solo&start=0&count=20
  - riotId must be "GameName#TAG" (e.g., MK1Paris#NA1)
  - mode: all | solo | flex | normal | aram | clash
  """
  if "#" not in riotId:
    raise HTTPException(400, "riotId must be formatted as Name#TAG (e.g., MK1Paris#NA1)")

  game_name, tag_line = riotId.split("#", 1)
  count = max(1, min(count, 50))  # clamp for safety

  async with RiotClient() as rc:
    # 1) lookup PUUID
    try:
      puuid = await rc.puuid_by_riot_id(region, game_name, tag_line)
    except Exception as e:
      raise HTTPException(400, f"Account lookup failed: {e}")

    # 2) get match IDs (server-side queue filter iff single queue)
    queues = None if mode.lower() == "all" else QUEUES.get(mode.lower())
    try:
      if queues and len(queues) == 1:
        ids = await rc.match_ids(region, puuid, start, count, queue=queues[0])
      else:
        raw = await rc.match_ids(region, puuid, start, count)
        if queues:
          # client-side filter by queue (extra detail calls)
          ids = []
          for mid in raw:
            m = await rc.match(region, mid)
            if m.get("info", {}).get("queueId", -1) in queues:
              ids.append(mid)
        else:
          ids = raw
    except Exception as e:
      raise HTTPException(400, f"Match ID lookup failed: {e}")

    # 3) build brief list
    briefs = []
    for mid in ids:
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

      briefs.append(MatchBrief(
          matchId=mid,
          queueId=info.get("queueId", -1),
          gameMode=info.get("gameMode", ""),
          durationSec=info.get("gameDuration", you.get("timePlayed", 0) if you else 0),
          patch=patch,                    # <-- include
          you=youb
      ))

    nextStart = start + len(ids)
    return MatchesResponse(
        region=region, riotId=riotId, puuid=puuid,
        mode=mode, start=start, nextStart=nextStart, matches=briefs
    )
