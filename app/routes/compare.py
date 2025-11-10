# app/routes/compare.py
from fastapi import APIRouter, HTTPException
from typing import Any, Dict, Optional, Tuple, List
import math, json

from app.bedrock_client import call_claude_json

router = APIRouter(prefix="/api", tags=["compare"])

# ---- Rank weighting (stronger on tier/div/LP as requested) ----
TIER_ELO = {
  "iron": 400, "bronze": 600, "silver": 800, "gold": 1000,
  "platinum": 1200, "emerald": 1400, "diamond": 1600,
  "master": 1800, "grandmaster": 1950, "challenger": 2100,
}
DIV_STEP = 80            # ↑ from 50
LP_SCALE = 2.0           # ↑ from 1

def _as_percent(x: Any) -> float:
  """
  Accepts 0.53, "0.53", 53, "53%", etc.
  Returns 53.0 (i.e., 0..100 scale).
  """
  if x is None:
    return 0.0
  if isinstance(x, str):
    s = x.strip()
    if s.endswith("%"):
      try:
        return float(s[:-1])
      except Exception:
        return 0.0
    try:
      v = float(s)
    except Exception:
      return 0.0
  else:
    try:
      v = float(x)
    except Exception:
      return 0.0
  # If it looks like 0..1, treat as fraction -> percent
  return v * 100.0 if 0.0 <= v <= 1.0 else v

def _normalize_profile(p: Dict[str, Any]) -> Dict[str, Any]:
  """
  Accepts either legacy shape:
    { year: { overall, bestChamp, topChamps }, currentRank }
  or new v1 export:
    { version:"v1", playerId, rank, overall, bestChamp, topChamps }
  Returns a normalized dict:
    { "rank": {...}, "overall": {...}, "bestChamp": {...}, "topChamps": [...] }
  """
  if not isinstance(p, dict):
    return {"rank": {}, "overall": {}, "bestChamp": {}, "topChamps": []}

  # v1?
  if p.get("version") == "v1" or ("overall" in p and "rank" in p):
    rank = p.get("rank") or {}
    overall = p.get("overall") or {}
    # ensure % fields are 0..100
    overall_norm = {
      "winrate": _as_percent(overall.get("winrate")),
      "kda": float(overall.get("kda") or 0),
      "csPerMin": float(overall.get("csPerMin") or 0),
      "visionPerMin": float(overall.get("visionPerMin") or 0),
      "primaryRole": overall.get("primaryRole"),
    }
    return {
      "rank": rank,
      "overall": overall_norm,
      "bestChamp": p.get("bestChamp") or {},
      "topChamps": p.get("topChamps") or [],
    }

  # legacy
  year = p.get("year") or {}
  overall = (year.get("overall") or {})
  rank = p.get("currentRank") or {}
  overall_norm = {
    "winrate": _as_percent(overall.get("winrate")),
    "kda": float(overall.get("kda") or 0),
    "csPerMin": float(overall.get("csPerMin") or 0),
    "visionPerMin": float(overall.get("visionPerMin") or 0),
    "primaryRole": overall.get("primaryRole"),
  }
  return {
    "rank": rank,
    "overall": overall_norm,
    "bestChamp": year.get("bestChamp") or {},
    "topChamps": year.get("topChamps") or [],
  }

def rank_to_elo(r: Optional[Dict[str, Any]]) -> int:
  if not r or not r.get("tier"):
    return 0
  base = TIER_ELO.get(str(r["tier"]).lower(), 0)
  div = str(r.get("division", "")).upper()
  div_score = 3 if div == "I" else 2 if div == "II" else 1 if div == "III" else 0
  lp = float(r.get("lp", 0) or 0)
  return int(base + div_score * DIV_STEP + lp * LP_SCALE)

def perf_score(n: Dict[str, Any]) -> float:
  o = n.get("overall") or {}
  wr = float(o.get("winrate") or 0)       # already normalized to 0..100
  kda = float(o.get("kda") or 0)
  cs  = float(o.get("csPerMin") or 0)
  vis = float(o.get("visionPerMin") or 0)
  # keep modest influence
  return wr * 2.0 + kda * 8.0 + cs * 2.0 + vis * 1.5

def prior_anchor(a_raw: Dict[str, Any], b_raw: Dict[str, Any]) -> Tuple[float, Dict[str, Any], Dict[str, Any]]:
  """
  Normalize both profiles, compute rank-heavy anchor win% for A.
  Returns (anchor_pct, a_norm, b_norm)
  """
  a = _normalize_profile(a_raw)
  b = _normalize_profile(b_raw)

  elo_w, perf_w = 0.85, 0.15  # rank/LP much heavier
  a_rating = elo_w * rank_to_elo(a.get("rank")) + perf_w * perf_score(a)
  b_rating = elo_w * rank_to_elo(b.get("rank")) + perf_w * perf_score(b)
  diff = a_rating - b_rating

  # logistic on rating diff (scale governs sensitivity)
  p = 1.0 / (1.0 + math.exp(-diff / 200.0))
  return round(p * 100.0, 1), a, b

def _pack_for_llm(n: Dict[str, Any]) -> Dict[str, Any]:
  """Keep it compact but explicit for Claude."""
  return {
    "rank": n.get("rank") or {},
    "overall": n.get("overall") or {},
    "bestChamp": n.get("bestChamp") or {},
    "topChamps": (n.get("topChamps") or [])[:5],
  }

@router.post("/compare-claude")
def compare_claude(payload: Dict[str, Any]):
  a_raw = payload.get("aProfile")
  b_raw = payload.get("bProfile")
  if not a_raw or not b_raw:
    raise HTTPException(400, "Provide aProfile and bProfile")

  anchor, a_norm, b_norm = prior_anchor(a_raw, b_raw)

  system = (
    "You are Rift Rewind Judge. Compare two League players based ONLY on provided profiles.\n"
    "Heavily weight competitive rank (tier/division/LP). Use performance stats as a secondary factor.\n"
    "START from the provided 'anchorWinPctYou' (already rank-weighted) and adjust at most ±10 points based on\n"
    "winrate/KDA/CS/min/vision and clear champion-pool/role signals. Return STRICT JSON:\n"
    "{ winPctYou: number(0..100), summary: string, reasons: string[] } — no extra keys."
  )

  user = json.dumps({
    "anchorWinPctYou": anchor,
    "you": _pack_for_llm(a_norm),
    "opponent": _pack_for_llm(b_norm),
    "notes": [
      "Prefer higher tier/division/LP strongly.",
      "Use stats only to nudge, not override rank.",
      "Do not exceed ±10 points from anchor."
    ]
  }, ensure_ascii=False)

  raw = call_claude_json(system, user, max_tokens=500, temperature=0.1)

  # Tolerant parse: raw may be a dict, a stringified JSON, or wrapped
  out: Dict[str, Any] = {}
  try:
    if isinstance(raw, dict):
      # Try direct, or common wrappers (e.g., outputText)
      if {"winPctYou", "reasons"} <= set(raw.keys()):
        out = raw
      else:
        txt = raw.get("outputText") or raw.get("completion") or raw.get("result") or ""
        out = json.loads(txt) if txt else {}
    elif isinstance(raw, str):
      out = json.loads(raw)
  except Exception:
    out = {}

  # Fallbacks if model returned something unexpected
  win = out.get("winPctYou", anchor)
  try:
    win = float(win)
  except Exception:
    win = anchor

  # Clamp to ±10 pts of anchor
  lo, hi = anchor - 10.0, anchor + 10.0
  win = max(min(win, hi), lo)

  summary = out.get("summary") or "Verdict weighted by rank/LP with minor performance adjustments."
  reasons = out.get("reasons") or [
    "Higher competitive rank carries the most weight in outcome prediction.",
    "Performance statistics (winrate/KDA/CS/vision) considered as small adjustments.",
  ]

  return {
    "aWinPct": round(win, 1),
    "summary": summary,
    "reasons": reasons[:6],
    "anchor": anchor
  }
