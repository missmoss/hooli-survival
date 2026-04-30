# Hooli Survival

Hooli Survival is a browser-based office survival sim built with a Next.js frontend and a FastAPI backend.

Read about how I [Build Hooli Survival: Software Controls State, AI Tells Stories](https://clairetsao.substack.com/p/building-hooli-survival-software?r=w4jh)

## What Exists Today

- The player starts a session, receives a generated opening scene, and plays through short project and event scenes.
- The game tracks persistent state across scenes, including `tech`, `visibility`, `affinity`, `pip_potential`, and cycle counters.
- Special scenes include performance review, promotion, PIP, quit flow, and reorg.
- The UI supports English and Traditional Chinese.
- Dev mode supports perf review fixture sessions via `?dev=true`.

## AI Runtime

- Story generation runtime uses `gemini-2.5-flash` first.
- If Gemini is unavailable, it falls back to `claude-haiku-4-5-20251001`.

## Repo Layout

```text
frontend/   Next.js app
backend/    FastAPI app, game logic, prompts, persistence
DEPLOYMENT.md
```

## Local Development

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend defaults to `http://localhost:3000` and backend defaults to `http://localhost:8000`.

## Notes

- Local default DB is SQLite.
