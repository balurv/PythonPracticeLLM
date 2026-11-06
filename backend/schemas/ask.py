from pydantic import BaseModel


class AskRequest(BaseModel):
    message: str
    agent_id: int | None = None


class AskResponse(BaseModel):
    reply: str
