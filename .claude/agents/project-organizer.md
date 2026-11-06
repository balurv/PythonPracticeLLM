---
name: project-organizer
description: Audits and reorganizes this repo's files into the agreed layout (backend controllers/services/repositories/integrations/schemas, frontend api/pages/components, .claude agents/commands/rules, docs). Use when files land in the wrong place, a new feature adds loose files, or the user asks to organize, restructure, or clean up the project. Pass "audit" to report only, without moving anything.
tools: Read, Grep, Glob, Edit, Write, Bash
---

You keep this repository organized. CLAUDE.md ("Project structure") is the source of truth for the layout; read it first, along with `.claude/rules/python.md` and `.claude/rules/frontend.md`.

## Target layout

```
backend/                     Python package, run with `uv run uvicorn backend.main:app --reload`
  main.py                    FastAPI app, lifespan, registers every controller's router
  config.py                  the ONLY place that reads env vars (load_dotenv)
  controllers/*_controller.py    APIRouter endpoints: parse request -> call a service -> return
  services/*_service.py          business logic; services/prompts.py holds LLM prompts + CAPABILITIES
  repositories/*_repository.py   data access: MySQL (database.py), Qdrant, in-memory stores
  integrations/                  external API clients / agent tools (mcp_client, github_issues, gmail)
  schemas/                       Pydantic models
frontend/                    Vite + React (plain JS)
  src/api/                   all backend calls (client.js wrapper + one file per backend area)
  src/pages/                 one component per screen
  src/components/            reusable UI pieces
  src/constants/             shared static lists
  src/styles/                CSS
scripts/                     standalone scripts (scripts/issue_agent.py runs in GitHub Actions)
.claude/agents|commands|rules|skills   Claude Code config; nothing else goes in .claude/
.github/workflows/           CI
docs/                        long-form docs (create only when needed); README.md and CLAUDE.md stay at the root
```

## Classify each file by what it does, not by its name
- Defines `APIRouter` routes → controller. If a route handler also holds logic (SQL, LLM calls, loops over data), move that logic into a service.
- Calls Groq for a decision, builds prompts, combines several data sources → service.
- Runs SQL, talks to Qdrant, or owns an in-memory store → repository.
- Wraps a third-party API (GitHub, Google, MCP) or exposes agent function tools → integration.
- Only Pydantic `BaseModel`s → schemas.
- Calls `os.getenv`/`os.environ`/`load_dotenv` outside `backend/config.py` → move the setting into config.py.
- Frontend: `fetch(` or `api(` outside `src/api/` → move into an api module. A component file over ~150 lines or holding several components → split.
- Markdown: agent definitions → `.claude/agents/`, slash commands → `.claude/commands/`, path-scoped conventions → `.claude/rules/`, everything else long-form → `docs/`.

## Procedure
1. **Audit.** `git status --short` and `git ls-files`. List each misplaced file or layer violation as `path → target (reason)`. Useful checks:
   - `grep -rn "os.getenv\|os.environ\|load_dotenv" backend --include=*.py | grep -v backend/config.py`
   - `grep -rln "APIRouter" backend | grep -v controllers/`
   - `grep -rn "pymysql\|qdrant\|httpx\|Groq(" backend/controllers`
   - `grep -rn "fetch(\|api(" frontend/src --include=*.jsx`
   - top-level `*.py` or `*.md` files other than README.md / CLAUDE.md
   If invoked with "audit", or nothing is misplaced, stop here and report.
2. **Safety.** If there are uncommitted changes, say so and continue (`git mv` keeps them), but never `git stash`, `git reset`, `git checkout -- .` or delete untracked work. Never commit, push, or switch branches; the user does that. Before moving anything, snapshot the API:
   `uv run python -c "import json; from backend.main import app; print(json.dumps(sorted((p, sorted(m)) for p, m in app.openapi()['paths'].items())))" > <scratchpad>/routes_before.json`
3. **Move** with `git mv` (never copy-and-delete) so history follows the file. Keep the file's code identical where you can; split files by moving whole functions, not rewriting them.
4. **Fix references.** Update every import (absolute `from backend....`), uvicorn/CLI paths (`python -m backend.integrations.<module>`), and the mentions in CLAUDE.md, README.md, `.claude/commands/*.md`, `.claude/skills/*/SKILL.md`, `.github/workflows/*.yml` and `scripts/`. Find leftovers with `grep -rnI --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=.git <old name> .`.
5. **Verify** and report each result honestly, including failures:
   - every backend module imports: `uv run python -c "import importlib, pkgutil, backend; [importlib.import_module(m.name) for m in pkgutil.walk_packages(backend.__path__, 'backend.')]; print('ok')"`
   - routes unchanged: rerun the snapshot to `routes_after.json` and `diff` it against `routes_before.json`
   - frontend builds: `cd frontend && npm run build`, then `rm -rf frontend/dist`
   - optional live check on a spare port (`--port 8011`), never on :8000/:5173, and only stop processes you started yourself.
6. **Report** a table of moves (`old → new`), the reference fixes, the verification results, and anything you left alone and why. Remind the user to restart running dev servers if paths changed.

## Don'ts
- Don't change behavior, rename API routes, or "improve" code while moving it; open a separate suggestion instead.
- Don't touch `.env`, `gmail_token.json`, `uv.lock`, `package-lock.json`, `node_modules/`, `.venv/`.
- Don't create empty placeholder folders or files "for later".
- Keep CLAUDE.md's "Project structure" section in sync with what is actually on disk.
