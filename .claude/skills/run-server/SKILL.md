---
name: run-server
description: Start the FastAPI dev server and smoke-test the /ask endpoint. Use when asked to run, start, or verify the app.
---

1. Make sure `.env` exists with `GROQ_API_KEY` (copy from `.env.example` if missing; ask the user for the key, never invent one).
2. Start the server in the background: `uv run uvicorn backend.main:app --reload`
3. Test it:
   `curl -X POST localhost:8000/ask -H "Content-Type: application/json" -d '{"message":"Hello"}'`
4. Report the reply, or the error if the call failed.
