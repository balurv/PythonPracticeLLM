# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview
Minimal FastAPI service that forwards a user message to an LLM via the Groq API. Managed with `uv`, Python 3.13.

## Commands
```bash
uv sync                              # install deps into .venv
cp .env.example .env                 # then set GROQ_API_KEY
uv run uvicorn main:app --reload     # dev server on :8000 (Swagger UI at /docs)
uv run python mcp_client.py "<prompt>"   # Groq LLM + GitHub MCP tools (needs GITHUB_PAT)
uv add <pkg>                         # add a dependency (updates pyproject.toml + uv.lock)
curl -X POST localhost:8000/ask -H "Content-Type: application/json" -d '{"message":"Hello"}'
```
No test suite or linter is configured yet.

## Architecture
- All app code is in `main.py` at the repo root: a module-level `Groq` client and a single `POST /ask` endpoint (`{"message"}` → `{"reply"}`) that makes one non-streaming chat completion call.
- Config comes from env vars loaded via `python-dotenv` from `.env`: `GROQ_API_KEY` (required), `GROQ_MODEL` (default `openai/gpt-oss-120b`). `GROQ_API_KEY` is also exported in the user's `~/.zshrc`, so `.env` is optional locally; `load_dotenv` does not override existing env vars.
- `mcp_client.py` is a standalone MCP client: it connects to the remote GitHub MCP server (`https://api.githubcopilot.com/mcp/`) with `GITHUB_PAT`, exposes an allowlist of tools (`MCP_TOOLS`) to Groq as function tools, and loops on tool calls (max 10 steps). The allowlist exists because Groq's free tier caps requests at ~8k tokens/min and the full GitHub toolset exceeds that. Uses `mcp` SDK 2.x APIs (`streamable_http_client`, `Tool.input_schema`).
- `src/groq_llm/__init__.py` and the `groq-llm` script in `pyproject.toml` are leftover `uv init` scaffolding (hello-world stub), not the service. Uvicorn targets `main:app`, not the package.
