---
description: Start Qdrant, the FastAPI backend (:8000) and the React frontend (:5173)
allowed-tools: Bash(lsof:*), Bash(uv sync:*), Bash(uv run uvicorn:*), Bash(curl:*), Bash(docker start demo-qdrant-1), Bash(npm install:*), Bash(npm run dev:*)
---

Start this project. Never kill an existing process yourself; if a port is taken, report it and skip that step.

1. **Qdrant**: `docker start demo-qdrant-1`, then check `curl -s localhost:6333` responds.
2. **MySQL**: check `lsof -nP -iTCP:3306 -sTCP:LISTEN` or a quick connection test. If MySQL is down, tell me to start it (System Settings → MySQL → Start); don't try to start it with sudo.
3. **Backend**: if nothing listens on :8000, run `uv sync`, then in the background (run_in_background) `uv run uvicorn main:app --reload`. `GROQ_API_KEY`, `GEMINI_API_KEY` and `GITHUB_PAT` come from `~/.zshrc` or `.env`. Wait until `curl -s -o /dev/null -w "%{http_code}" localhost:8000/docs` returns 200 (~10s), else show the server output and stop.
4. **Frontend**: if nothing listens on :5173, run `npm install` in `web/` (only if `web/node_modules` is missing), then in the background `npm run dev` in `web/`. Wait until `localhost:5173` responds.
5. Report:
   - Web app: http://localhost:5173
   - API: http://localhost:8000 (Swagger UI: http://localhost:8000/docs)
   - Try it: `/ask <message>`
