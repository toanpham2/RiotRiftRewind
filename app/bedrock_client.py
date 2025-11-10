# app/bedrock_client.py
import os
import json
import hashlib
import boto3
import re
import logging
from typing import Optional
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, ParamValidationError

from app.config import AWS_REGION, BEDROCK_MODEL_ID

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
log = logging.getLogger("bedrock_client")
if not log.handlers:
  h = logging.StreamHandler()
  h.setFormatter(logging.Formatter("[BR] %(levelname)s: %(message)s"))
  log.addHandler(h)
  log.setLevel(logging.INFO)

# -----------------------------------------------------------------------------
# Env toggles
# -----------------------------------------------------------------------------
OFFLINE = os.getenv("OFFLINE_CLAUDE", "").strip() == "1"
PROFILE_ARN = os.getenv("BEDROCK_INFERENCE_PROFILE_ARN", "").strip()
AWS_PROFILE = os.getenv("AWS_PROFILE") or None

# -----------------------------------------------------------------------------
# Cache & helpers
# -----------------------------------------------------------------------------
_CL = None  # bedrock client singleton
_CACHE: dict[str, str] = {}  # key -> response text (stringified JSON for JSON calls)
_JSON_OBJECT_AT_END = re.compile(r"\{[\s\S]*\}\s*$")

def _cache_key(system_prompt: str, user_prompt: str, max_tokens: int, temperature: float, suffix: str = "") -> str:
  h = hashlib.sha256()
  h.update(system_prompt.encode("utf-8")); h.update(b"\x00")
  h.update(user_prompt.encode("utf-8"));   h.update(b"\x00")
  h.update(str(max_tokens).encode("ascii")); h.update(b"\x00")
  h.update(str(temperature).encode("ascii")); h.update(b"\x00")
  h.update(suffix.encode("utf-8"))
  return h.hexdigest()

def _client():
  """Create/reuse a Bedrock Runtime client with sensible timeouts + retries."""
  global _CL
  if _CL is not None:
    return _CL

  if OFFLINE:
    _CL = object()  # placeholder
    return _CL

  session = boto3.Session(profile_name=AWS_PROFILE)
  cfg = Config(
      retries={"max_attempts": 4, "mode": "standard"},
      connect_timeout=5,
      read_timeout=30,
  )
  _CL = session.client("bedrock-runtime", region_name=AWS_REGION, config=cfg)
  return _CL

def _extract_text(resp: dict) -> str:
  """
  Bedrock Converse response -> first text block.
  Expected:
  {
    "output": {
      "message": {
        "role": "...",
        "content": [{"text": "..."}]
      }
    }
  }
  """
  out = (resp or {}).get("output") or {}
  msg = out.get("message") or {}
  for block in (msg.get("content") or []):
    if isinstance(block, dict) and "text" in block:
      return block["text"]
  return json.dumps(out) if out else ""

def _offline_stub(system_prompt: str, user_prompt: str) -> str:
  return (
    "You play to your champ’s strengths—clean mechanics, steady vision, and clutch mid-game calls. "
    "Keep locking your comfort picks and tighten your ward timers; you’re closer than you think."
  )

# -----------------------------------------------------------------------------
# Plain text helper (used by routes that just want text back)
# -----------------------------------------------------------------------------
def coach_with_claude(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 600,
    temperature: float = 0.6,
    *,
    use_cache: bool = True,
) -> str:
  if OFFLINE:
    return _offline_stub(system_prompt, user_prompt)

  key: Optional[str] = None
  if use_cache:
    key = _cache_key(system_prompt, user_prompt, max_tokens, temperature, suffix="|TEXT")
    hit = _CACHE.get(key)
    if hit is not None:
      return hit

  req = {
    "messages": [{"role": "user", "content": [{"text": user_prompt}]}],
    "system": [{"text": system_prompt}],
    "inferenceConfig": {
      "maxTokens": max_tokens,
      "temperature": float(temperature),
    },
  }

  try:
    cl = _client()
    if PROFILE_ARN:
      resp = cl.converse(modelId=PROFILE_ARN, **req)
    else:
      resp = cl.converse(modelId=BEDROCK_MODEL_ID, **req)
    text = _extract_text(resp) or ""
  except (BotoCoreError, ClientError, ParamValidationError) as e:
    log.error("Bedrock text call failed: %s", e)
    text = (
      "I couldn’t reach the AI coach just now. "
      "Focus on one role, 1–2 champions, and keep vision ≥ 0.9/min for your next 10 games."
    )

  if use_cache and key is not None and text:
    _CACHE[key] = text
  return text

# -----------------------------------------------------------------------------
# JSON helpers
# -----------------------------------------------------------------------------
def _extract_json_dict(text: str) -> dict:
  if not text:
    return {}
  try:
    return json.loads(text)
  except Exception:
    pass
  m = _JSON_OBJECT_AT_END.search(text)
  if m:
    try:
      return json.loads(m.group(0))
    except Exception:
      return {}
  return {}

def call_claude_json(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 700,
    temperature: float = 0.2,
    *,
    use_cache: bool = True,
    retry_plaintext_on_empty: bool = True,
) -> dict:
  """
  Robust JSON caller:
  1) Try Bedrock JSON mode (responseFormat={"type":"json"}).
  2) If empty/invalid, retry in plaintext mode with a strict JSON-only instruction,
     then tolerantly parse the last {...} block.
  Returns a Python dict (possibly empty if both attempts fail).
  """
  if OFFLINE:
    return {
      "summary": "Offline stub: concise summary.",
      "laningPlan": ["Play fundamentals.", "Respect spikes."],
      "trading": ["Trade on cooldown windows."],
      "wave": ["Crash when winning, hold when losing."],
      "wards": ["Pixel brush, tri, river."],
      "withJungle": ["Stack wave before dive."],
      "winConditions": ["Herald → plates."],
      "commonMistakes": ["Fighting without prio."],
      "skillTips": ["Weave autos."],
      "itemization": ["Build for enemy damage type."],
      "runes": ["Standard page."],
      "timers": ["Lvl 3, 6, first item."],
      "quickChecklist": ["Track jg.", "Crash on cannon.", "Hold TP."],
    }

  # ---------- Attempt 1: Bedrock JSON mode ----------
  json_key: Optional[str] = None
  parsed: dict = {}

  if use_cache:
    json_key = _cache_key(system_prompt, user_prompt, max_tokens, temperature, suffix="|JSONMODE")
    hit = _CACHE.get(json_key)
    if hit is not None:
      try:
        parsed = json.loads(hit)
        log.info("JSON mode cache hit")
        return parsed
      except Exception:
        parsed = {}

  req_json = {
    "messages": [{"role": "user", "content": [{"text": user_prompt}]}],
    "system": [{"text": system_prompt}],
    "inferenceConfig": {"maxTokens": max_tokens, "temperature": float(temperature)},
    "responseFormat": {"type": "json"},
  }

  text = ""
  try:
    cl = _client()
    if PROFILE_ARN:
      resp = cl.converse(modelId=PROFILE_ARN, **req_json)
    else:
      resp = cl.converse(modelId=BEDROCK_MODEL_ID, **req_json)
    text = _extract_text(resp) or ""
    log.info("JSON mode response len=%d", len(text))
  except (BotoCoreError, ClientError, ParamValidationError) as e:
    log.error("Bedrock JSON call failed: %s", e)
    text = ""

  parsed = _extract_json_dict(text)
  if parsed:
    if use_cache and json_key is not None:
      _CACHE[json_key] = json.dumps(parsed, ensure_ascii=False)
    return parsed

  # ---------- Attempt 2: Plain-text mode with strict JSON instruction ----------
  if not retry_plaintext_on_empty:
    log.warning("JSON mode returned empty and retry is disabled.")
    return {}

  # Strengthen the instruction to force a bare JSON object.
  strict_system = (
      system_prompt
      + "\n\nYou MUST return ONLY a single JSON object with the required keys. "
        "No prose, no code fences, no explanations—just the JSON."
  )

  pt_key: Optional[str] = None
  if use_cache:
    pt_key = _cache_key(strict_system, user_prompt, max_tokens, temperature, suffix="|PLAINTEXTJSONRETRY")
    hit = _CACHE.get(pt_key)
    if hit is not None:
      try:
        parsed_retry = json.loads(hit)
        log.info("Plain-text retry cache hit")
        return parsed_retry
      except Exception:
        pass

  req_text = {
    "messages": [{"role": "user", "content": [{"text": user_prompt}]}],
    "system": [{"text": strict_system}],
    "inferenceConfig": {"maxTokens": max_tokens, "temperature": float(temperature)},
  }

  text_retry = ""
  try:
    cl = _client()
    if PROFILE_ARN:
      resp = cl.converse(modelId=PROFILE_ARN, **req_text)
    else:
      resp = cl.converse(modelId=BEDROCK_MODEL_ID, **req_text)
    text_retry = _extract_text(resp) or ""
    log.info("Plain-text retry response len=%d head=%s", len(text_retry), text_retry[:120].replace("\n", " "))
  except (BotoCoreError, ClientError, ParamValidationError) as e:
    log.error("Plain-text retry failed: %s", e)
    text_retry = ""

  parsed_retry = _extract_json_dict(text_retry)
  if use_cache and pt_key is not None:
    _CACHE[pt_key] = json.dumps(parsed_retry, ensure_ascii=False)
  if not parsed_retry:
    log.warning("Plain-text retry still produced empty/invalid JSON.")
  return parsed_retry
