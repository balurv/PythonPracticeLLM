import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from groq import Groq
from pydantic import BaseModel

load_dotenv()  # before importing modules that read env vars at import time

import db  # noqa: E402
import orchestrator  # noqa: E402
import vectors  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Keep /ask usable even if MySQL or Qdrant is down; agent routes will fail until they're up.
    for name, init in (("MySQL", db.init), ("Qdrant", vectors.init)):
        try:
            init()
        except Exception as e:
            logging.getLogger("uvicorn.error").warning("%s not ready: %s", name, e)
    yield


app = FastAPI(lifespan=lifespan)
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# Include books router
from books import router as books_router
app.include_router(books_router)
app.include_router(orchestrator.router)


class Ask(BaseModel):
    message: str
    agent_id: int | None = None


@app.post("/ask")
def ask(req: Ask):
    if req.agent_id is not None:
        return {"reply": orchestrator.chat(req.agent_id, req.message)}
    res = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": req.message}],
    )
    return {"reply": res.choices[0].message.content}
