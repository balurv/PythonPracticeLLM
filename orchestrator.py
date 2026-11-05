"""Agent orchestrator: reuse a matching agent or create a new one, and chat with agents.

Matching is two-step: Qdrant finds the most similar existing agents, then one
Groq call decides whether one of them fits the request or a new agent is needed.
"""

import asyncio
import json
import os
from typing import Literal

import groq
from fastapi import APIRouter, HTTPException
from groq import Groq
from pydantic import BaseModel, Field

import db
import mcp_client
import tool_issues
import vectors

router = APIRouter(tags=["agents"])
# The SDK default timeout is 10 minutes; fail fast instead so the web UI doesn't hang.
client = Groq(api_key=os.getenv("GROQ_API_KEY"), timeout=60)
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
MEMORY_TURNS = 6
MEMORY_CHARS = 1500  # per remembered message; long old replies would blow Groq's free-tier TPM cap

Mechanism = Literal["rag", "memory", "github", "gmail_inbox_reader"]

# Every tool an agent can be given. A capability not listed here gets a GitHub issue instead.
CAPABILITIES = {
    "rag": "search knowledge text the user pasted for this agent",
    "memory": "remember earlier messages in this conversation",
    "github": "GitHub: read the user's profile, list/read/create issues, comment, list pull requests, read repo files",
    "gmail_inbox_reader": "Read a user's Gmail inbox, extract receipt and expense details for analysis",
}
CATALOG = "\n".join(f"- {k}: {v}" for k, v in CAPABILITIES.items())

DECIDE = f"""You are an agent orchestrator. Given a user's agent request and up to 3 existing
agents (with similarity scores), decide whether an existing agent already fits the request.
Reuse only if its purpose and skills clearly match; otherwise create a new agent.

Agents are an LLM that can reason and write, plus only these tools:
{CATALOG}
If the request needs access to something none of these provide (e.g. reading an email inbox,
browsing the web, a calendar, a bank or payments API), list each missing tool in "missing_tools"
with a full specification for the dev team who will build it. Otherwise use [].
Always check this, for both reuse and create: reusing an agent does not give it new tools.

Reply with JSON only:
{{"action": "reuse", "agent_id": <id>, "reason": "<one sentence>", "missing_tools": [...]}}
or
{{"action": "create", "name": "<short agent name>", "system_prompt": "<instructions for the new
agent: role, skills, requirements, tone; 3-6 sentences>", "reason": "<one sentence>", "missing_tools": [...]}}

Each missing tool: {{"name": "<snake_case_tool_name>", "purpose": "<what it does and why the agent
needs it>", "inputs": ["<param: type, meaning>"], "output": "<what it returns>",
"acceptance_criteria": ["<testable criterion>"], "security_notes": ["<credentials, read-only, privacy>"]}}"""

NO_TOOL_RULE = """HARD RULE: you can only act through the tools listed under "Your tools".
If a request needs any other access (email, web, files, calendar, bank, APIs...), do NOT write code,
scripts, setup guides or API instructions for it, even if the user asks for code. Instead call the
`request_tool` function with a full specification: it files a GitHub issue in the project's own repo
(already configured, never ask the user for an owner or repository) so the dev team can build it.
Tool and capability requests must always go through `request_tool`, never through GitHub tools like
`issue_write` (those are only for the user's own GitHub tasks).
Then reply briefly that the capability isn't available yet and share the issue link it returns.
If the tool is already listed under "Requested tools", just share that link. You may still help with
any part that needs no new tool."""

REMINDER = (
    "Reminder: follow the HARD RULE. No code or how-to for capabilities outside your tools; "
    "use request_tool (never issue_write; repo is preconfigured) and share the issue link."
)

REQUEST_TOOL_SPEC = {
    "name": "request_tool",
    "description": "File a GitHub issue asking the dev team to build a tool this agent lacks. "
    "The repository is preconfigured. Always use this (not issue_write) for tool requests. "
    "Returns the issue link.",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "snake_case tool name, e.g. email_inbox_reader"},
            "purpose": {"type": "string", "description": "what it does and why the user needs it"},
            "inputs": {"type": "array", "items": {"type": "string"}, "description": "param: type, meaning"},
            "output": {"type": "string", "description": "what the tool returns"},
            "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
            "security_notes": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["name", "purpose"],
    },
}


class AgentRequest(BaseModel):
    name: str | None = None
    requirements: str = Field(min_length=1)
    skills: list[str] = []
    knowledge: str | None = None
    mechanisms: list[Mechanism] = []


def decide(req: AgentRequest, candidates: list[dict]) -> dict:
    listing = "\n".join(
        f"- id {c['id']} (score {c['score']:.2f}): {c['name']}: {c['description']} "
        f"Skills: {', '.join(c['skills'])}"
        for c in candidates
    ) or "(none)"
    res = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": DECIDE},
            {"role": "user", "content": (
                f"Request:\nName: {req.name or '-'}\nRequirements: {req.requirements}\n"
                f"Skills: {', '.join(req.skills) or '-'}\n\nExisting agents:\n{listing}"
            )},
        ],
        response_format={"type": "json_object"},
        reasoning_effort="low",
    )
    return json.loads(res.choices[0].message.content)


def request_missing_tools(agent: dict, tools: list[dict]) -> list[dict]:
    """File (or find) a GitHub issue per missing tool and link it to the agent."""
    filed = []
    for tool in tools:
        if not isinstance(tool, dict) or not tool.get("name"):
            continue
        try:
            issue = tool_issues.request_tool(tool, agent)
        except Exception as e:  # no token, no permission, GitHub down: report, don't fail the request
            filed.append({"name": tool["name"], "error": f"Could not file issue: {e}"})
            continue
        db.add_tool_request(agent["id"], tool["name"], issue["number"], issue["url"])
        filed.append({"name": tool["name"], **issue})
    return filed


@router.post("/orchestrate")
def orchestrate(req: AgentRequest):
    return friendly_groq_errors(_orchestrate, req)


def _orchestrate(req: AgentRequest):
    query = f"{req.name or ''} {req.requirements} Skills: {', '.join(req.skills)}"
    candidates = []
    for agent_id, score in vectors.similar_agents(query):
        if agent := db.get_agent(agent_id):
            candidates.append({**agent, "score": score})

    decision = decide(req, candidates)
    ids = {c["id"] for c in candidates}
    if decision.get("action") == "reuse" and decision.get("agent_id") in ids:
        agent = db.get_agent(decision["agent_id"])
        # Turn on any newly requested mechanisms for the reused agent.
        merged = sorted(set(agent["mechanisms"]) | set(req.mechanisms))
        if merged != sorted(agent["mechanisms"]):
            db.update_mechanisms(agent["id"], merged)
            agent["mechanisms"] = merged
        action = "reuse"
    else:
        agent = db.create_agent(
            name=req.name or decision.get("name") or "Agent",
            description=req.requirements,
            system_prompt=decision.get("system_prompt") or req.requirements,
            skills=req.skills,
            requirements=req.requirements,
            mechanisms=req.mechanisms,
        )
        vectors.index_agent(agent)
        action = "create"

    chunks = vectors.add_knowledge(agent["id"], req.knowledge) if req.knowledge else 0
    tool_requests = request_missing_tools(agent, decision.get("missing_tools") or [])
    agent["tool_requests"] = db.tool_requests(agent["id"])
    return {
        "action": action,
        "reason": decision.get("reason", ""),
        "agent": agent,
        "knowledge_chunks": chunks,
        "tool_requests": tool_requests,
    }


@router.get("/agents")
def list_agents():
    return db.list_agents()


@router.get("/agents/{agent_id}/messages")
def agent_messages(agent_id: int):
    if not db.get_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    return db.messages(agent_id)


def _groq_error(e: BaseException) -> groq.APIStatusError | None:
    """Find a Groq API error, including inside the ExceptionGroups the MCP task group raises."""
    if isinstance(e, groq.APIStatusError):
        return e
    for sub in getattr(e, "exceptions", ()):
        if found := _groq_error(sub):
            return found
    return None


def chat(agent_id: int, message: str) -> str:
    return friendly_groq_errors(_chat, agent_id, message)


def friendly_groq_errors(fn, *args):
    """Turn Groq API errors into clear HTTP errors instead of a bare 500."""
    try:
        return fn(*args)
    except Exception as e:
        err = _groq_error(e)
        if err is None:
            raise
        if err.status_code in (413, 429):
            raise HTTPException(
                status_code=429,
                detail="Groq free-tier limit hit (8k tokens/min). Wait a minute and retry, "
                "or turn off GitHub tools for this agent to make requests smaller.",
            ) from e
        raise HTTPException(status_code=502, detail=f"Groq error: {err.message}") from e


def _chat(agent_id: int, message: str) -> str:
    agent = db.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    mech = set(agent["mechanisms"])

    tools = [f"- {m}: {CAPABILITIES[m]}" for m in agent["mechanisms"] if m in CAPABILITIES]
    system = NO_TOOL_RULE + "\n\nYour tools:\n" + ("\n".join(tools) or "- none (text only)")
    system += f"\n\nYour role:\n{agent['system_prompt']}"
    if agent["skills"]:
        system += f"\nSkills: {', '.join(agent['skills'])}."
    if agent["requirements"]:
        system += f"\nRequirements: {agent['requirements']}"
    if agent["tool_requests"]:
        system += "\nRequested tools (not available yet):\n" + "\n".join(
            f"- {t['name']}: {t['issue_url']}" for t in agent["tool_requests"]
        )
    if "rag" in mech and (chunks := vectors.search_knowledge(agent_id, message)):
        system += "\n\nUse this knowledge when relevant:\n" + "\n---\n".join(chunks)

    messages = [{"role": "system", "content": system}]
    if "memory" in mech:
        messages += [
            {"role": m["role"], "content": m["content"][:MEMORY_CHARS]}
            for m in db.recent_messages(agent_id, MEMORY_TURNS)
        ]
    messages.append({"role": "user", "content": message})
    messages.append({"role": "system", "content": REMINDER})

    def request_tool(**tool) -> str:
        filed = request_missing_tools(agent, [tool])[0]
        return filed.get("error") or (
            f"Issue #{filed['number']} {'created' if filed['created'] else 'already open'}: {filed['url']}"
        )

    local_tools = {"request_tool": (REQUEST_TOOL_SPEC, request_tool)}
    reply = asyncio.run(mcp_client.ask_with_tools(messages, local_tools, github="github" in mech))

    if "memory" in mech:
        db.add_message(agent_id, "user", message)
        db.add_message(agent_id, "assistant", reply)
    return reply
