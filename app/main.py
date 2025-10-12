import os
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.routes.matches import router as matches_router
from app.routes.coach import router as coach_router

import sys, os, boto3, botocore

print("[Startup] Python:", sys.executable)
print("[Startup] boto3:", boto3.__version__, "botocore:", botocore.__version__)
print("[Startup] AWS_REGION:", os.getenv("AWS_REGION"))
print("[Startup] BEDROCK_INFERENCE_PROFILE_ARN:", os.getenv("BEDROCK_INFERENCE_PROFILE_ARN"))
app = FastAPI(title = "Rift Rewind Hackathon")

#health check
@app.get("/api/health", response_class = PlainTextResponse)
async def health():
    return "ok"

#register API routes
app.include_router(matches_router)
app.include_router(coach_router)

#static frontend
static_dir = os.path.join(os.path.dirname(__file__),"static")
app.mount("/", StaticFiles(directory=static_dir, html = True), name = "static")