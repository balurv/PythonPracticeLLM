import os

from dotenv import load_dotenv
from fastapi import FastAPI
from groq import Groq
from pydantic import BaseModel

load_dotenv()
app = FastAPI()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# Include books router
from books import router as books_router
app.include_router(books_router)


class Ask(BaseModel):
    message: str


@app.post("/ask")
def ask(req: Ask):
    res = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": req.message}],
    )
    return {"reply": res.choices[0].message.content}
