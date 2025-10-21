import os
from dotenv import load_dotenv

load_dotenv()

RIOT_API_KEY = os.getenv("RIOT_API_KEY")
if not RIOT_API_KEY:
  raise RuntimeError("Missing RIOT_API_KEY in environment")

REGIONAL = {
  "americas": "americas.api.riotgames.com",
  "europe":   "europe.api.riotgames.com",
  "asia":     "asia.api.riotgames.com",
  "sea":      "sea.api.riotgames.com",
}

#UI-game mode
QUEUES = {
  "solo": [420],
  "flex": [440],
  "normal": [400, 430],
  "aram": [450],
  "clash": [700],
}

#BedRock
AWS_REGION =os.getenv("AWS_REGION", "us-east-2")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0")

# app/config.py
# app/config.py

SPLITS = {
  # TODO: adjust patch ranges to your exact window once final
  "s1": ("15.1",  "15.8"),
  "s2": ("15.9",  "15.16"),
  "s3": ("15.17", "15.24"),
}


