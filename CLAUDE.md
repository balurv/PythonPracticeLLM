# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview
Minimal FastAPI service that forwards a user message to an LLM via the Groq API, plus an "agent hub": an orchestrator that reuses or creates LLM agents, with a React frontend in `web/`. Managed with `uv`, Python 3.13.

Agent features need MySQL (`root`/`root` on `127.0.0.1:3306`, DB `agent_hub` auto-created) and Qdrant (`docker start demo-qdrant-1` → `:6333`). Plain `/ask` works without them; startup only logs a warning.

## Commands
```bash
uv sync                              # install deps into .venv
cp .env.example .env                 # then set GROQ_API_KEY
uv run uvicorn main:app --reload     # dev server on :8000 (Swagger UI at /docs)
uv run python mcp_client.py "<prompt>"   # Groq LLM + GitHub MCP tools (needs GITHUB_PAT)
uv add <pkg>                         # add a dependency (updates pyproject.toml + uv.lock)
curl -X POST localhost:8000/ask -H "Content-Type: application/json" -d '{"message":"Hello"}'
cd web && npm install && npm run dev # React app on :5173 (proxies /api → :8000)
```
No test suite or linter is configured yet.

## Architecture
- `main.py`: app entry. `POST /ask` (`{"message", "agent_id"?}` → `{"reply"}`): without `agent_id` it's one plain Groq call; with it, it delegates to `orchestrator.chat`. `load_dotenv()` runs before importing `db`/`vectors`/`orchestrator`, which read env at import. A lifespan handler creates the MySQL tables and Qdrant collections.
- `orchestrator.py`: `POST /orchestrate` finds the top-3 similar agents in Qdrant, then one Groq JSON-mode call decides `reuse` (merging newly requested mechanisms) or `create` (LLM writes the system prompt); optional `knowledge` text is embedded for the chosen agent. Also `GET /agents`, `GET /agents/{id}/messages`, and `chat()`, which applies the agent's mechanisms: `rag` (top-3 Qdrant chunks in the system prompt), `memory` (last 6 MySQL messages, saved after each reply), `github` (tool loop via `mcp_client.ask_with_tools`).
- Missing tools: `CAPABILITIES` in `orchestrator.py` is the catalog of tools agents can have. The decide call also returns `missing_tools` (full specs) for capabilities outside that catalog, and `tool_issues.py` files one GitHub issue per tool (label `tool-request`, deduped by title among open issues; needs `GITHUB_PAT` with Issues: write) for the dev team to build; links are stored in the `tool_requests` table. In chat, every agent also gets a local `request_tool` function (preconfigured repo, same issue format and dedupe), and a hard rule (start of the system prompt, plus a reminder after the user turn) stops agents from writing code for capabilities they lack; they file or link the issue instead. `mcp_client.run` takes `local_tools` (name → (spec, fn)) and works without an MCP session for non-GitHub agents. To ship a new tool: add it to `CAPABILITIES`, the `Mechanism` literal, `chat()`, and the web checkbox list.
- `db.py`: pymysql helpers; tables `agents` (skills/mechanisms as JSON), `messages`, `tool_requests`.
- `vectors.py`: Qdrant collections `agents` and `knowledge` (768-dim cosine) with Gemini embeddings (`gemini-embedding-001`, `GEMINI_API_KEY`); knowledge is split into ~500-char chunks and searched with an `agent_id` filter.
- `web/`: Vite + React, plain JS, whole UI in `src/App.jsx` (agent request form, agent list, chat). Calls the backend through the Vite `/api` proxy, so the backend has no CORS config.
- Config comes from env vars loaded via `python-dotenv` from `.env`: `GROQ_API_KEY` (required), `GROQ_MODEL` (default `openai/gpt-oss-120b`). `GROQ_API_KEY` is also exported in the user's `~/.zshrc`, so `.env` is optional locally; `load_dotenv` does not override existing env vars.
- `mcp_client.py` is an MCP client (CLI, and `ask_with_tools(messages)` for agents): it connects to the remote GitHub MCP server (`https://api.githubcopilot.com/mcp/`) with `GITHUB_PAT`, exposes an allowlist of tools (`MCP_TOOLS`) to Groq as function tools, and loops on tool calls (max 10 steps). If Groq rejects a call with `tool_use_failed` (the model wrote invalid tool-call JSON, e.g. curly quotes), `_complete` retries up to 2 times with a correction hint. The allowlist exists because Groq's free tier caps requests at ~8k tokens/min and the full GitHub toolset exceeds that. Uses `mcp` SDK 2.x APIs (`streamable_http_client`, `Tool.input_schema`).
- `src/groq_llm/__init__.py` and the `groq-llm` script in `pyproject.toml` are leftover `uv init` scaffolding (hello-world stub), not the service. Uvicorn targets `main:app`, not the package.
