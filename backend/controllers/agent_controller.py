"""POST /orchestrate, GET /agents, GET /agents/{id}/messages."""

from fastapi import APIRouter

from backend.schemas.agent import AgentRequest
from backend.services import agent_service

router = APIRouter(tags=["agents"])


@router.post("/orchestrate")
def orchestrate(req: AgentRequest):
    return agent_service.orchestrate(req)


@router.get("/agents")
def list_agents():
    return agent_service.list_agents()


@router.get("/agents/{agent_id}/messages")
def agent_messages(agent_id: int):
    return agent_service.agent_messages(agent_id)
