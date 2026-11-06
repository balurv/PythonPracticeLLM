# PythonPracticeLLM: Agent Hub

FastAPI + Groq backend with an agent orchestrator, and a React frontend.

```bash
uv sync
cp .env.example .env                        # add your GROQ_API_KEY (and others for agent features)
uv run uvicorn backend.main:app --reload    # API on :8000, Swagger UI at /docs
cd frontend && npm install && npm run dev   # web app on :5173
curl -X POST localhost:8000/ask -H "Content-Type: application/json" -d '{"message":"Hello"}'
```

## Layout
- `backend/`: `controllers/` (HTTP routes) → `services/` (logic) → `repositories/` (MySQL, Qdrant) and `integrations/` (GitHub, Gmail, MCP); `schemas/` for Pydantic models; `config.py` for env vars.
- `frontend/src/`: `api/` (backend calls), `pages/`, `components/`, `constants/`, `styles/`.
- `scripts/`: GitHub Actions issue agent. `.claude/`: Claude Code agents, commands, rules and skills.

See [CLAUDE.md](CLAUDE.md) for architecture details. Run `/organize` in Claude Code to keep files in place.
