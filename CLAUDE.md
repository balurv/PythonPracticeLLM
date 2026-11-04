# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview
Minimal FastAPI service that forwards a user message to an LLM via the Groq API. Managed with `uv`, Python 3.13.

## Commands
```bash
uv sync                              # install deps into .venv
cp .env.example .env                 # then set GROQ_API_KEY
uv run uvicorn main:app --reload     # dev server on :8000 (Swagger UI at /docs)
uv add <pkg>                         # add a dependency (updates pyproject.toml + uv.lock)
curl -X POST localhost:8000/ask -H "Content-Type: application/json" -d '{"message":"Hello"}'
```
No test suite or linter is configured yet.

## Architecture
- All app code is in `main.py` at the repo root: a module-level `Groq` client and a single `POST /ask` endpoint (`{"message"}` → `{"reply"}`) that makes one non-streaming chat completion call.
- Config comes from env vars loaded via `python-dotenv` from `.env`: `GROQ_API_KEY` (required), `GROQ_MODEL` (default `llama-3.3-70b-versatile`).
- `src/groq_llm/__init__.py` and the `groq-llm` script in `pyproject.toml` are leftover `uv init` scaffolding (hello-world stub), not the service. Uvicorn targets `main:app`, not the package.
