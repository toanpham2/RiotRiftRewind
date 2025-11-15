# RiotRiftRewind
Riot Game's and AWS Hackathon codebase

Rift Rewind analyzes a player’s entire match history, extracts gameplay patterns, evaluates strengths & weaknesses, and generates personalized coaching insights using Riot’s Match V5 API and AWS Bedrock (Claude 3.5 Sonnet).

This repository contains all backend + frontend source code, assets, and instructions required for the project to run locally or in production.

---

# Getting Started (Local)

## Backend (FastAPI)

### 1. Activate Environment
```bash
cd RiftRewindHackathon
python -m venv .venv && source .venv/bin/activate
# Windows: .venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Add Environment Variables
Copy:
```bash
cp .env.example .env
```
Fill in:
- RIOT_API_KEY  
- AWS_ACCESS_KEY_ID  
- AWS_SECRET_ACCESS_KEY  
- BEDROCK_MODEL_ID  
- BEDROCK_INFERENCE_PROFILE_ARN  

 Do NOT commit `.env`.

### 4. Start Backend
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Backend docs available at:  
http://localhost:8000/docs

---

## Frontend (Vite + React + TypeScript)

### 1. Install Dependencies
```bash
cd frontend
npm i     # or pnpm i
```

### 2. Add Frontend Environment Variables
Copy:
```bash
cp .env.example .env
```

Set:
```
VITE_API_URL=/api
```

### 3. Start Dev Server
```bash
npm run dev
```

Click the local Vite URL shown in terminal.

---

# Deployment

### Backend  
- Hosted on **Render** (Python Web Service)

### Frontend  
- Hosted on **Vercel**  
- Root directory: `frontend/`  
- Path rewrites forward `/api/*` → Render backend

### Production URL (Public)  
**https://riot-rift-rewind.vercel.app/**

---

#  Cold Start Delay (Free Tier Hosting)

Because the backend performs:
- Full match-history aggregation (100–200+ matches)
- Multi-stage analytics + ranking
- Multiple AI generations via AWS Bedrock

…Render **spins down** when idle on the free tier.

So the **first request after inactivity** will be slow.

### If you see a temporary `502` or `Router External Target Error` on the *first run*:
 Quick Rewind → wait **3–5 minutes**, then click once more  
 Full Rewind → wait **5–12 minutes**, then click again  

Once the backend warms up, subsequent runs are much faster.

This behavior is normal for free-tier serverless hosting.

---

# Features

### Match Analysis
- Full rewind for year wise analysis
- Quick rewind (most recent 100 matches for purpose of testing)
- Fetches full match history via Riot Match V5  
- Role and champion detection  
- Trading & laning metrics  
- Wave control & macro evaluation  
- Objective impact tracking  
- Win conditions & risk mapping 

### AI Coaching via AWS Bedrock
- Personalized gameplay breakdown  
- Strengths & weaknesses  
- Matchup advice  
- Champion pool recommendations  
- Fun, motivational champion-themed quotes  

### Frontend UI
- League-themed interface (gold + dark style)  
- Smooth animations  
- Riot ID input flow  
- Quick Rewind / Full Rewind report generation  

---

# Tech Stack

### Backend
- Python  
- FastAPI  
- httpx  
- asyncio  
- Uvicorn  
- Riot Games API (Match V5, Account V1, League V4)

### AI / ML
- AWS Bedrock  
- Claude 3.5 Sonnet  
- Bedrock Inference Profiles

### Frontend
- React  
- Vite  
- TypeScript  
- TailwindCSS (custom theme)

### Hosting
- Render (backend)  
- Vercel (frontend)

---

# Environment Variables

### `.env.example` (Backend)
```
RIOT_API_KEY=

AWS_REGION=us-east-2
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
BEDROCK_MODEL_ID=
BEDROCK_INFERENCE_PROFILE_ARN=
```

### `frontend/.env.example`
```
VITE_API_URL=/api
```

---

# License

Licensed under the **MIT License**.  
A `LICENSE` file is included at the root.

---

# Folder Structure

```
/
├── app/                     # FastAPI backend
├── frontend/                # Vercel-hosted UI
├── requirements.txt
├── package.json
├── .env.example
├── LICENSE
└── README.md
```

---

# Contact

Created by **Toan Pham**  
GitHub: https://github.com/toanpham2

