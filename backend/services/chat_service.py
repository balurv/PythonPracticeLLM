"""Chat with an agent: build its system prompt and apply its mechanisms.

Mechanisms: `rag` (top-3 Qdrant chunks in the system prompt), `memory` (last 6 MySQL messages,
saved after each reply), `github` (GitHub MCP tools), `gmail` (read-only Gmail tools),
`maps` (places and routes), `fitness` (exercise plans).
Every agent also gets the local `request_tool` function for capabilities it lacks.
"""

import asyncio

from fastapi import HTTPException

from backend.integrations import fitness, gmail, maps, mcp_client
from backend.repositories import agent_repository, message_repository, vector_repository
from backend.services import llm_service
from backend.services.prompts import CAPABILITIES, NO_TOOL_RULE, REMINDER, REQUEST_TOOL_SPEC
from backend.services.tool_request_service import request_missing_tools

MEMORY_TURNS = 6
MEMORY_CHARS = 1500  # per remembered message; long old replies would blow Groq's free-tier TPM cap


def chat(agent_id: int, message: str) -> str:
    return llm_service.friendly_groq_errors(_chat, agent_id, message)


def _system_prompt(agent: dict, mech: set[str], message: str) -> str:
    tools = [f"- {m}: {CAPABILITIES[m]}" for m in agent["mechanisms"] if m in CAPABILITIES]
    system = NO_TOOL_RULE + "\n\nYour tools:\n" + ("\n".join(tools) or "- none (text only)")
    if off := [f"- {m}: {d}" for m, d in CAPABILITIES.items() if m not in mech]:
        system += (
            "\n\nBuilt but not enabled for you (if the user needs one, tell them to turn it on: submit the "
            "agent form again with this agent's name and tick it; don't call request_tool for these):\n"
            + "\n".join(off)
        )
    system += f"\n\nYour role:\n{agent['system_prompt']}"
    if agent["skills"]:
        system += f"\nSkills: {', '.join(agent['skills'])}."
    if agent["requirements"]:
        system += f"\nRequirements: {agent['requirements']}"
    if agent["tool_requests"]:
        system += "\nRequested tools (filed earlier; if one of Your tools now covers it, use that tool instead):\n" + "\n".join(
            f"- {t['name']}: {t['issue_url']}" for t in agent["tool_requests"]
        )
    if "rag" in mech and (chunks := vector_repository.search_knowledge(agent["id"], message)):
        system += "\n\nUse this knowledge when relevant:\n" + "\n---\n".join(chunks)
    return system


def _chat(agent_id: int, message: str) -> str:
    agent = agent_repository.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    mech = set(agent["mechanisms"])

    messages = [{"role": "system", "content": _system_prompt(agent, mech, message)}]
    if "memory" in mech:
        messages += [
            {"role": m["role"], "content": m["content"][:MEMORY_CHARS]}
            for m in message_repository.recent_messages(agent_id, MEMORY_TURNS)
        ]
    messages.append({"role": "user", "content": message})
    messages.append({"role": "system", "content": REMINDER})

    def request_tool(**tool) -> str:
        text = f"{tool.get('name', '')} {tool.get('purpose', '')}".lower()
        if built := next((m for m in CAPABILITIES if m in text), None):
            if built in mech:
                return f"Not filed: you already have the '{built}' tool. Use its functions now instead."
            return (
                f"Not filed: the '{built}' tool already exists but isn't enabled for this agent. Tell the user "
                f"to submit the agent form again with this agent's name and tick '{built}'."
            )
        filed = request_missing_tools(agent, [tool])[0]
        return filed.get("error") or (
            f"Issue #{filed['number']} {'created' if filed['created'] else 'already open'}: {filed['url']}"
        )

    local_tools = {"request_tool": (REQUEST_TOOL_SPEC, request_tool)}
    for name, module in (("gmail", gmail), ("maps", maps), ("fitness", fitness)):
        if name in mech:
            local_tools |= module.TOOLS
    reply = asyncio.run(mcp_client.ask_with_tools(messages, local_tools, github="github" in mech))

    if "memory" in mech:
        message_repository.add_message(agent_id, "user", message)
        message_repository.add_message(agent_id, "assistant", reply)
    return reply
