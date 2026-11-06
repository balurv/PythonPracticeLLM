"""Agent orchestration: reuse a matching agent or create a new one; list agents and their messages.

Matching is two-step: Qdrant finds the most similar existing agents, then one
Groq call decides whether one of them fits the request or a new agent is needed.
"""

import json

from fastapi import HTTPException

from backend.repositories import agent_repository, message_repository, vector_repository
from backend.schemas.agent import AgentRequest
from backend.services import llm_service
from backend.services.prompts import DECIDE
from backend.services.tool_request_service import request_missing_tools


def decide(req: AgentRequest, candidates: list[dict]) -> dict:
    listing = "\n".join(
        f"- id {c['id']} (score {c['score']:.2f}): {c['name']}: {c['description']} "
        f"Skills: {', '.join(c['skills'])}"
        for c in candidates
    ) or "(none)"
    res = llm_service.client.chat.completions.create(
        model=llm_service.MODEL,
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


def orchestrate(req: AgentRequest) -> dict:
    return llm_service.friendly_groq_errors(_orchestrate, req)


def _orchestrate(req: AgentRequest) -> dict:
    query = f"{req.name or ''} {req.requirements} Skills: {', '.join(req.skills)}"
    candidates = []
    for agent_id, score in vector_repository.similar_agents(query):
        if agent := agent_repository.get_agent(agent_id):
            candidates.append({**agent, "score": score})

    decision = decide(req, candidates)
    ids = {c["id"] for c in candidates}
    if decision.get("action") == "reuse" and decision.get("agent_id") in ids:
        agent = agent_repository.get_agent(decision["agent_id"])
        # Turn on any newly requested mechanisms for the reused agent.
        merged = sorted(set(agent["mechanisms"]) | set(req.mechanisms))
        if merged != sorted(agent["mechanisms"]):
            agent_repository.update_mechanisms(agent["id"], merged)
            agent["mechanisms"] = merged
        action = "reuse"
    else:
        agent = agent_repository.create_agent(
            name=req.name or decision.get("name") or "Agent",
            description=req.requirements,
            system_prompt=decision.get("system_prompt") or req.requirements,
            skills=req.skills,
            requirements=req.requirements,
            mechanisms=req.mechanisms,
        )
        vector_repository.index_agent(agent)
        action = "create"

    chunks = vector_repository.add_knowledge(agent["id"], req.knowledge) if req.knowledge else 0
    tool_requests = request_missing_tools(agent, decision.get("missing_tools") or [])
    agent["tool_requests"] = agent_repository.tool_requests(agent["id"])
    return {
        "action": action,
        "reason": decision.get("reason", ""),
        "agent": agent,
        "knowledge_chunks": chunks,
        "tool_requests": tool_requests,
    }


def list_agents() -> list[dict]:
    return agent_repository.list_agents()


def agent_messages(agent_id: int) -> list[dict]:
    if not agent_repository.get_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    return message_repository.messages(agent_id)
