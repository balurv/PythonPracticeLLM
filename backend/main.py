"""FastAPI app entry: `uv run uvicorn backend.main:app --reload`.

Layers: controllers/ (HTTP) -> services/ (logic) -> repositories/ (MySQL, Qdrant, memory)
and integrations/ (Groq tool loop, GitHub, Gmail). Settings live in config.py.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.controllers import agent_controller, ask_controller, book_controller, gmail_controller
from backend.repositories import database, vector_repository


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Keep /ask usable even if MySQL or Qdrant is down; agent routes will fail until they're up.
    for name, init in (("MySQL", database.init), ("Qdrant", vector_repository.init)):
        try:
            init()
        except Exception as e:
            logging.getLogger("uvicorn.error").warning("%s not ready: %s", name, e)
    yield


app = FastAPI(title="Agent Hub", lifespan=lifespan)

for controller in (ask_controller, agent_controller, gmail_controller, book_controller):
    app.include_router(controller.router)
