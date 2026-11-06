from typing import Literal

from pydantic import BaseModel, Field

# Agent tools. Keep in sync with CAPABILITIES in services/prompts.py and the frontend's constants/mechanisms.js.
Mechanism = Literal["rag", "memory", "github", "gmail", "maps", "fitness"]


class AgentRequest(BaseModel):
    name: str | None = None
    requirements: str = Field(min_length=1)
    skills: list[str] = []
    knowledge: str | None = None
    mechanisms: list[Mechanism] = []
