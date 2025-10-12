from fastapi import APIRouter, HTTPException
from collections import Counter
from app.riot_client import RiotClient
from app.bedrock_client import coach_with_claude

router = APIRouter(tags=["coach"])

def _compact_metrics(matches: list[dict]) -> dict:
  n = len(matches) or 1
  k = sum(m["you"]["kills"] for m in matches)
  d = sum(m["you"]["deaths"] for m in matches)
  a = sum(m["you"]["assists"] for m in matches)
  wins = sum(1 for m in matches if m["you"]["win"])
  return {
    "games": n,
    "avg_k": round(k/n, 2),
    "avg_d": round(d/n, 2),
    "avg_a": round(a/n, 2),
    "winrate": round(100*wins/n, 1)
  }

@router.get("/api/coach")
async def coach(region: str, riotId: str, mode: str = "all", count: int = 10):
  if "#" not in riotId:
    raise HTTPException(400, "riotId must be formatted as Name#TAG (e.g., MK1Paris#NA1)")
  name, tag = riotId.split("#", 1)
  count = max(5, min(count, 20))

  brief = []
  async with RiotClient() as rc:
    puuid = await rc.puuid_by_riot_id(region, name, tag)
    ids = await rc.match_ids(region, puuid, 0, count)
    for mid in ids:
      m = await rc.match(region, mid)
      info = m.get("info", {})
      you = next((p for p in info.get("participants", []) if p.get("puuid") == puuid), None)
      brief.append({
        "matchId": mid,
        "gameMode": info.get("gameMode", ""),
        "durationSec": info.get("gameDuration", you.get("timePlayed", 0) if you else 0),
        "you": {
          "champion": you.get("championName", "") if you else "",
          "kills": you.get("kills", 0) if you else 0,
          "deaths": you.get("deaths", 0) if you else 0,
          "assists": you.get("assists", 0) if you else 0,
          "win": bool(you.get("win")) if you else False,
        }
      })

  metrics = _compact_metrics(brief)
  main_champ = (Counter([m["you"]["champion"] for m in brief if m["you"]["champion"]]).most_common(1) or [(None,0)])[0][0] or "Unknown"

  system = (
    "You are Rift Rewind, a concise League coach. "
    "Use the provided stats to give specific, actionable advice with measurable targets. "
    "Avoid generic tips."
  )
  user = (
    f"Region: {region}\nRiotId: {riotId}\n"
    f"Main champ (sample): {main_champ}\n"
    f"Games: {metrics['games']} | Winrate: {metrics['winrate']}%\n"
    f"Avg K/D/A: {metrics['avg_k']}/{metrics['avg_d']}/{metrics['avg_a']}\n\n"
    "Output:\n"
    "1) Two-sentence summary of strengths & one key weakness.\n"
    "2) Three bullets, each formatted as: [Action — Why — Measurable target].\n"
    "≤150 words total."
  )

  advice = coach_with_claude(system, user)
  return {"riotId": riotId, "champion": main_champ, "metrics": metrics, "advice": advice}
