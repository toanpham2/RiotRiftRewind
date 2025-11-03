# app/bedrock_client.py
import os
import json
import hashlib
import boto3
from typing import Optional
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, ParamValidationError

from app.config import AWS_REGION, BEDROCK_MODEL_ID

# -----------------------------------------------------------------------------
# Env toggles
# -----------------------------------------------------------------------------
# Set OFFLINE_CLAUDE=1 to stub out responses without calling Bedrock
OFFLINE = os.getenv("OFFLINE_CLAUDE", "").strip() == "1"
PROFILE_ARN = os.getenv("BEDROCK_INFERENCE_PROFILE_ARN", "").strip()
AWS_PROFILE = os.getenv("AWS_PROFILE") or None

# -----------------------------------------------------------------------------
# Simple in-proc cache to avoid re-calling Bedrock for identical prompts
# -----------------------------------------------------------------------------
_CL = None  # bedrock client singleton
_CACHE: dict[str, str] = {}  # key: sha256(system+user+params) -> text


def _cache_key(system_prompt: str, user_prompt: str, max_tokens: int, temperature: float) -> str:
  h = hashlib.sha256()
  h.update(system_prompt.encode("utf-8"))
  h.update(b"\x00")
  h.update(user_prompt.encode("utf-8"))
  h.update(b"\x00")
  h.update(str(max_tokens).encode("ascii"))
  h.update(b"\x00")
  h.update(str(temperature).encode("ascii"))
  return h.hexdigest()


def _client():
  """Create/reuse a Bedrock Runtime client with sensible timeouts + retries."""
  global _CL
  if _CL is not None:
    return _CL

  if OFFLINE:
    # No client needed in offline mode
    _CL = object()
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
  Shape typically:
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
  # Fallback to something printable for debugging
  return json.dumps(out) if out else ""


def _offline_stub(system_prompt: str, user_prompt: str) -> str:
  """
  Deterministic stub for local testing without AWS creds.
  You can customize this, or even branch on keywords to emulate different behaviors.
  """
  return (
    "You play to your champ’s strengths—clean mechanics, steady vision, and clutch mid-game calls. "
    "Keep locking your comfort picks and tighten your ward timers; you’re closer than you think."
  )


def coach_with_claude(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 600,
    temperature: float = 0.6,
    *,
    use_cache: bool = True,
) -> str:
  """
  Main entry: returns a plain string from Claude via Bedrock.
  - Honors OFFLINE_CLAUDE=1 to skip network calls.
  - Caches by (system, user, max_tokens, temperature) unless use_cache=False.
  """
  # Offline short-circuit (no AWS needed)
  if OFFLINE:
    return _offline_stub(system_prompt, user_prompt)

  # Cache
  key: Optional[str] = None
  if use_cache:
    key = _cache_key(system_prompt, user_prompt, max_tokens, temperature)
    hit = _CACHE.get(key)
    if hit is not None:
      return hit

  # Build request
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
      # Use an Inference Profile ARN if provided
      resp = cl.converse(modelId=PROFILE_ARN, **req)
    else:
      # Direct model call (e.g., "anthropic.claude-3-5-sonnet-20241022-v2:0")
      resp = cl.converse(modelId=BEDROCK_MODEL_ID, **req)
    text = _extract_text(resp) or ""
  except (BotoCoreError, ClientError, ParamValidationError) as e:
    # Don’t break your endpoint—return a safe, helpful fallback
    text = (
      "I couldn’t reach the AI coach just now. "
      "Focus on one role, 1–2 champions, and keep vision ≥ 0.9/min for your next 10 games."
    )

  # Save to cache
  if use_cache and key is not None and text:
    _CACHE[key] = text

  return text
