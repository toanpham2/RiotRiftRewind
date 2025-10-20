# app/bedrock_client.py
import os, json, boto3
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError, ParamValidationError
from app.config import AWS_REGION, BEDROCK_MODEL_ID

_PROFILE_ARN = os.getenv("BEDROCK_INFERENCE_PROFILE_ARN", "").strip()
_bedrock = None

def _client():
  global _bedrock
  if _bedrock:
    return _bedrock
  session = boto3.Session(profile_name=(os.getenv("AWS_PROFILE") or None))
  cfg = Config(retries={"max_attempts": 4, "mode": "standard"}, connect_timeout=5, read_timeout=30)
  _bedrock = session.client("bedrock-runtime", region_name=AWS_REGION, config=cfg)
  return _bedrock

def _extract_text(resp: dict) -> str:
  out = (resp or {}).get("output") or {}
  msg = out.get("message") or {}
  for block in (msg.get("content") or []):
    if isinstance(block, dict) and "text" in block:
      return block["text"]
  return json.dumps(out) if out else ""

def coach_with_claude(system_prompt: str, user_prompt: str, max_tokens: int = 600, temperature: float = 0.6) -> str:
  bedrock = _client()
  req = {
    "messages": [{"role": "user", "content": [{"text": user_prompt}]}],
    "system": [{"text": system_prompt}],
    "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature},
  }

  if _PROFILE_ARN:  # use profile via modelId (works across SDK versions)
    resp = bedrock.converse(modelId=_PROFILE_ARN, **req)
    return _extract_text(resp)

  # fallback: call a regular model by ID
  resp = bedrock.converse(modelId=BEDROCK_MODEL_ID, **req)
  return _extract_text(resp)

