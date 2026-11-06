"""File GitHub issues for tools the orchestrator needs but doesn't have.

The dev team picks these up, builds and tests the tool, then adds it as a mechanism.
"""

import httpx

from backend import config

REPO = config.GITHUB_REPO
LABEL = "tool-request"
API = f"https://api.github.com/repos/{REPO}/issues"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {config.github_pat()}",
        "Accept": "application/vnd.github+json",
    }


def _title(tool: dict) -> str:
    return f"Tool request: {tool['name']}"


def bullets(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items) or "- (not specified)"


def _body(tool: dict, agent: dict) -> str:
    return f"""## Tool request: `{tool['name']}`

Filed automatically by the agent orchestrator: an agent needs this capability and no existing tool provides it.

## Purpose
{tool.get('purpose', '')}

## Requested by
Agent **#{agent['id']} {agent['name']}**. Its requirements:
> {(agent.get('requirements') or '').replace(chr(10), chr(10) + '> ')}

## Inputs (tool parameters)
{bullets(tool.get('inputs', []))}

## Output
{tool.get('output', '')}

## Acceptance criteria
{bullets(tool.get('acceptance_criteria', []))}

## Implementation notes
- Expose it as a new agent mechanism, like `gmail` (`backend/integrations/gmail.py`, wired in `backend/services/chat_service.py`) (function tools for the Groq tool loop).
- Read credentials from env vars (`.env` / `~/.zshrc`), never from the database or code. Add them to `.env.example`.
- Prefer read-only access; keep tool results small (Groq free tier is ~8k tokens/min).
{bullets(tool.get('security_notes', []))}
"""


def find_open(tool: dict) -> dict | None:
    res = httpx.get(API, headers=_headers(), params={"state": "open", "labels": LABEL, "per_page": 100}, timeout=20)
    res.raise_for_status()
    title = _title(tool).lower()
    return next((i for i in res.json() if i["title"].lower() == title), None)


def request_tool(tool: dict, agent: dict) -> dict:
    """Return the open issue for this tool, creating it if needed: {number, url, created}."""
    if issue := find_open(tool):
        return {"number": issue["number"], "url": issue["html_url"], "created": False}
    res = httpx.post(
        API,
        headers=_headers(),
        json={"title": _title(tool), "body": _body(tool, agent), "labels": [LABEL]},
        timeout=20,
    )
    if res.status_code == 403:
        raise PermissionError(
            f"GITHUB_PAT can't create issues in {REPO}. Give the token 'Issues: Read and write' permission."
        )
    res.raise_for_status()
    issue = res.json()
    return {"number": issue["number"], "url": issue["html_url"], "created": True}
