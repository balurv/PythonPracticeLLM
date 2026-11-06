---
paths:
  - "**/*.py"
---

# Python conventions
- Manage dependencies with `uv add`, never `pip install`.
- Read config only in `backend/config.py` (env vars via `python-dotenv`); other modules import from it. Add new keys to `.env.example`.
- Imports are absolute from the package root: `from backend.services import chat_service`.
- Respect the backend layers (see CLAUDE.md "Project structure"):
  - `controllers/`: FastAPI `APIRouter`s only. Parse the request, call one service, return. No SQL, no Groq/HTTP clients.
  - `services/`: business logic and LLM prompts. Call repositories and integrations, never another controller.
  - `repositories/`: data access only (MySQL, Qdrant, in-memory). No business rules, no FastAPI imports.
  - `integrations/`: clients for external APIs and agent tools (Groq tool loop/MCP, GitHub issues, Gmail).
  - `schemas/`: Pydantic request/response models.
- New router: add `<name>_controller.py` and register it in the loop in `backend/main.py`.
- Name files by layer: `<thing>_controller.py`, `<thing>_service.py`, `<thing>_repository.py`.
