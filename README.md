# RiotRiftRewind
Riot Game's and AWS hackathon codebase


## Getting Started (Local)

### Backend
1. `cd RiftRewindHackathon`
2. `python -m venv .venv && source .venv/bin/activate`  (Windows: `.venv\Scripts\activate`)
3. `pip install -r requirements.txt`  (or `pip install -r ../requirements.txt` if that’s your layout)
4. Copy `.env.example` to `.env` and fill in values (don’t commit `.env`).
5. `uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload`

API docs at http://localhost:8000/docs

### Frontend
1. `cd frontend`
2. `npm i` or `pnpm i`
3. Copy `.env.example` to `frontend/.env` and set `VITE_API_URL=/api`
4. `npm run dev` (Vite dev server)
5.  `click on the local link` 

## Deployment
- Backend: Render (Python Web Service), 
- Frontend: Vercel (Root: `frontend/`)
 

## Public url:
https://riot-rift-rewind.vercel.app/

Note on Initial Load Time (Cold Start)

Because the backend performs full-match historical analysis and AI-powered breakdowns, the first request may take longer while the service initializes ("cold start").

If you see a temporary 502 or Router External Target error on the FIRST run:

- Wait 2–5 minutes for Quick Rewind
- Wait 5–10 minutes for Full Rewind
- Click the button again, the request will succeed once the backend is warm.

This is normal behavior for serverless deployments using free-tier hosting, where backend containers spin down when idle.

Once warmed up, subsequent requests run alot smoother.
