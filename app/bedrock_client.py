# app/bedrock_client.py
import os
import boto3

from app.config import AWS_REGION, BEDROCK_MODEL_ID

# Read once at import
PROFILE_ARN = os.getenv("BEDROCK_INFERENCE_PROFILE_ARN", "").strip()

# Bedrock runtime client in the region you’re running
bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)


def coach_with_claude(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 600,
    temperature: float = 0.6,
) -> str:
  """
  Preferred path: Bedrock Converse with inferenceProfileArn (for Claude 3.5 Sonnet cross-region in us-east-2).
  Fallback: Converse with modelId (works for models that allow on-demand modelId).
  """
  # Converse request
  req = {
    "messages": [
      {"role": "user", "content": [{"text": user_prompt}]}
    ],
    # Anthropic expects system as a list of content blocks
    "system": [{"text": system_prompt}],
    "inferenceConfig": {
      "maxTokens": max_tokens,
      "temperature": temperature,
    },
  }

  # Prefer inference profile for Claude 3.5 Sonnet in us-east-2
  if PROFILE_ARN:
    resp = bedrock.converse(inferenceProfileArn=PROFILE_ARN, **req)
  else:
    # Fallback: call by modelId (works with models that support on-demand modelId)
    resp = bedrock.converse(modelId=BEDROCK_MODEL_ID, **req)

  # Extract the text safely
  out = resp.get("output", {})
  msg = out.get("message", {})
  for block in msg.get("content", []):
    if "text" in block:
      return block["text"]
  return ""
