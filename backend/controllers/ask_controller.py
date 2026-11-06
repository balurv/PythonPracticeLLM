"""POST /ask: plain LLM call, or chat with an agent when agent_id is given."""

from fastapi import APIRouter

from backend.schemas.ask import AskRequest, AskResponse
from backend.services import chat_service, llm_service

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    if req.agent_id is not None:
        return {"reply": chat_service.chat(req.agent_id, req.message)}
    return {"reply": llm_service.ask(req.message)}
