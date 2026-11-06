"""Groq client shared by all services, plain one-shot chat, and Groq error -> HTTP error mapping."""

import groq
from fastapi import HTTPException
from groq import Groq

from backend import config

client = Groq(api_key=config.GROQ_API_KEY, timeout=config.GROQ_TIMEOUT)
MODEL = config.GROQ_MODEL


def ask(message: str) -> str:
    """One plain LLM call, no agent (POST /ask without agent_id)."""
    res = client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": message}])
    return res.choices[0].message.content


def _groq_error(e: BaseException) -> groq.APIStatusError | None:
    """Find a Groq API error, including inside the ExceptionGroups the MCP task group raises."""
    if isinstance(e, groq.APIStatusError):
        return e
    for sub in getattr(e, "exceptions", ()):
        if found := _groq_error(sub):
            return found
    return None


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
