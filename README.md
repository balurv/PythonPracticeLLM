# groq-llm

```bash
cp .env.example .env   # add your GROQ_API_KEY
uv run uvicorn main:app --reload
curl -X POST localhost:8000/ask -H "Content-Type: application/json" -d '{"message":"Hello"}'
```
# PythonPracticeLLM
