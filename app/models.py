from pydantic import BaseModel, Field
from typing import List

class YouBrief(BaseModel):
  champion: str = ""
  kills: int = 0
  deaths: int = 0
  assists: int =0
  win: bool = False


class MatchBrief(BaseModel):
  matchId: str
  queueId: int
  gameMode: str = ""
  durationSec: int = 0
  you: YouBrief = Field(default_factory=YouBrief)


class MatchesResponse(BaseModel):
  region: str
  riotId: str
  puuid: str
  mode: str
  start: str
  nextStart: int
  matches: List[MatchBrief] = []


