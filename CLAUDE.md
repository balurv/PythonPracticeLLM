# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview
Agent Hub: a FastAPI backend (`backend/`) that forwards messages to an LLM via the Groq API, plus an orchestrator that reuses or creates LLM agents, with a React frontend (`frontend/`). Managed with `uv`, Python 3.13.

Agent features need MySQL (`root`/`root` on `127.0.0.1:3306`, DB `agent_hub` auto-created) and Qdrant (`docker start demo-qdrant-1` → `:6333`). Plain `/ask` works without them; startup only logs a warning.

## Commands
```bash
uv sync                                        # install deps into .venv
cp .env.example .env                           # then set GROQ_API_KEY
uv run uvicorn backend.main:app --reload       # dev server on :8000 (Swagger UI at /docs)
uv run python -m backend.integrations.mcp_client "<prompt>"   # Groq LLM + GitHub MCP tools (needs GITHUB_PAT)
uv run python -m backend.integrations.gmail search "<query>"  # Gmail tool CLI (after connecting Gmail)
uv add <pkg>                                   # add a dependency (updates pyproject.toml + uv.lock)
curl -X POST localhost:8000/ask -H "Content-Type: application/json" -d '{"message":"Hello"}'
cd frontend && npm install && npm run dev      # React app on :5173 (proxies /api → :8000)
```
No test suite or linter is configured yet. `/organize` (the `project-organizer` agent) audits and fixes the file layout below.

## Project structure
```
backend/
  main.py            app + lifespan (creates MySQL tables, Qdrant collections); registers routers
  config.py          every env var, read once (load_dotenv). Other modules import settings from here
  controllers/       HTTP layer (APIRouter): ask_controller (/ask), agent_controller (/orchestrate, /agents,
                     /agents/{id}/messages), gmail_controller (/gmail/*), book_controller (/books CRUD demo)
  services/          logic: llm_service (shared Groq client, Groq error → HTTP 429/502), agent_service
                     (orchestrate, list, messages), chat_service (agent chat + mechanisms),
                     tool_request_service (missing tools → issues), book_service, prompts (CAPABILITIES + prompts)
  repositories/      data: database (MySQL connect/query/schema), agent_repository (agents, tool_requests),
                     message_repository, vector_repository (Qdrant + Gemini embeddings), book_repository (in-memory)
  integrations/      external APIs / agent tools: mcp_client (Groq tool loop + GitHub MCP), github_issues, gmail, maps, fitness
  schemas/           Pydantic models: ask, agent (AgentRequest, Mechanism), book
frontend/src/
  main.jsx, App.jsx  entry; App renders the page
  api/               all backend calls: client.js (fetch wrapper, /api prefix), agents.js, gmail.js
  pages/             AgentHubPage (agent list + request form + chat)
  components/        AgentList, AgentForm, AgentChat, Linkify
  constants/         mechanisms.js (checkbox list)
  styles/            App.css
scripts/issue_agent.py   GitHub Actions issue agent (.github/workflows/claude-issue-agent.yml)
.claude/             agents/ (api-reviewer, project-organizer), commands/, rules/ (python, frontend), skills/
```
Layer rules: controllers → services → repositories/integrations, never backwards; details in `.claude/rules/python.md` and `.claude/rules/frontend.md`. Imports are absolute (`from backend.services import chat_service`). `pyproject.toml` sets `[tool.uv] package = false`: this is an app, not an installable package; uvicorn imports `backend` from the repo root.

## Architecture
- `POST /ask` (`{"message", "agent_id"?}` → `{"reply"}`): without `agent_id` it's one plain Groq call (`llm_service.ask`); with it, `chat_service.chat`.
- Orchestration (`agent_service.orchestrate`): finds the top-3 similar agents in Qdrant, then one Groq JSON-mode call (`DECIDE` prompt) decides `reuse` (merging newly requested mechanisms) or `create` (LLM writes the system prompt); optional `knowledge` text is embedded for the chosen agent.
- Chat (`chat_service`) applies the agent's mechanisms: `rag` (top-3 Qdrant chunks in the system prompt), `memory` (last 6 MySQL messages, saved after each reply), `github` (GitHub MCP tools), `gmail` (local Gmail tools), `maps` (OpenStreetMap places/routes), `fitness` (offline exercise catalog). The tool loop is `mcp_client.ask_with_tools`; `mcp_client.run` takes `local_tools` (name → (spec, fn)) and works without an MCP session for non-GitHub agents. Local tool exceptions are returned to the model as `Tool error: ...`.
- Missing tools: `CAPABILITIES` in `services/prompts.py` is the catalog of tools agents can have. The decide call also returns `missing_tools` (full specs) for capabilities outside it, and `tool_request_service` files one GitHub issue per tool via `integrations/github_issues.py` (label `tool-request`, deduped by title among open issues; needs `GITHUB_PAT` with Issues: write; repo `GITHUB_REPO`); links are stored in the `tool_requests` table. In chat, every agent also gets a local `request_tool` function (same issue format and dedupe), and a hard rule (`NO_TOOL_RULE` at the start of the system prompt, `REMINDER` after the user turn) stops agents from writing code for capabilities they lack; they file or link the issue instead. The prompt also lists catalog tools the agent doesn't have enabled, and `request_tool` refuses to file for any capability already in `CAPABILITIES` (it tells the agent to use it, or to ask the user to enable it via the agent form).
- To ship a new tool: add it to `CAPABILITIES` (`services/prompts.py`), the `Mechanism` literal (`schemas/agent.py`), `chat_service._chat`, and `frontend/src/constants/mechanisms.js`.
- Gmail (`integrations/gmail.py` + `controllers/gmail_controller.py`): read-only Gmail API (`gmail.readonly` scope) exposed as local tools `connect_gmail()`, `search_emails(query, max_results)` and `read_email(message_id)` (bodies trimmed to 3000 chars). When Gmail isn't connected the tool error hands the agent a link to `GET /gmail/connect`, which redirects to Google consent; `/gmail/callback` saves a refresh token to `gmail_token.json` (git-ignored, relative to the working directory); `GET /gmail/status` drives the frontend's "Connect Gmail" banner. Needs a Google OAuth "Web application" client (`GMAIL_CLIENT_ID`/`GMAIL_CLIENT_SECRET`) with `http://localhost:8000/gmail/callback` (`GMAIL_REDIRECT_URI`) in its Authorized redirect URIs. Pending sign-ins (state → PKCE verifier) live in memory, so a server reload mid-sign-in means starting again.
- MySQL tables: `agents` (skills/mechanisms as JSON), `messages`, `tool_requests`. Qdrant collections `agents` and `knowledge` (768-dim cosine) with Gemini embeddings (`gemini-embedding-001`, `GEMINI_API_KEY`); knowledge is split into ~500-char chunks and searched with an `agent_id` filter.
- `mcp_client` connects to the remote GitHub MCP server (`https://api.githubcopilot.com/mcp/`) with `GITHUB_PAT`, exposes an allowlist of tools (`MCP_TOOLS`) to Groq as function tools, and loops on tool calls (max 10 steps). If Groq rejects a call with `tool_use_failed` (invalid tool-call JSON, e.g. curly quotes), `_complete` retries up to 2 times with a correction hint. The allowlist exists because Groq's free tier caps requests at ~8k tokens/min and the full GitHub toolset exceeds that. Uses `mcp` SDK 2.x APIs (`streamable_http_client`, `Tool.input_schema`).
- Frontend: Vite + React, plain JS. Calls the backend through the Vite `/api` proxy, so the backend has no CORS config.
- Config: env vars from `.env` via `python-dotenv`, all in `backend/config.py`: `GROQ_API_KEY` (required), `GROQ_MODEL` (default `openai/gpt-oss-120b`), plus MySQL, Qdrant, Gemini, GitHub and Gmail keys (see `.env.example`). `GROQ_API_KEY` is also exported in the user's `~/.zshrc`, so `.env` is optional locally; `load_dotenv` does not override existing env vars.
