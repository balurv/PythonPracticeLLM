"""Qdrant vector store with Gemini embeddings: agent profiles and agent knowledge."""

import uuid

from google import genai
from google.genai import types
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

from backend import config

EMBED_MODEL = config.GEMINI_EMBED_MODEL
DIM = 768
AGENTS, KNOWLEDGE = "agents", "knowledge"
CHUNK = 500

qdrant = QdrantClient(url=config.QDRANT_URL)
_gemini: genai.Client | None = None


def embed(texts: list[str], task: str) -> list[list[float]]:
    """task: RETRIEVAL_DOCUMENT for stored text, RETRIEVAL_QUERY for searches."""
    global _gemini
    _gemini = _gemini or genai.Client(api_key=config.GEMINI_API_KEY)
    res = _gemini.models.embed_content(
        model=EMBED_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(task_type=task, output_dimensionality=DIM),
    )
    return [e.values for e in res.embeddings]


def init() -> None:
    for name in (AGENTS, KNOWLEDGE):
        if not qdrant.collection_exists(name):
            qdrant.create_collection(name, vectors_config=VectorParams(size=DIM, distance=Distance.COSINE))


def profile(agent: dict) -> str:
    return f"{agent['name']}. {agent.get('description') or ''} Skills: {', '.join(agent.get('skills') or [])}"


def index_agent(agent: dict) -> None:
    [vec] = embed([profile(agent)], "RETRIEVAL_DOCUMENT")
    qdrant.upsert(AGENTS, [PointStruct(id=agent["id"], vector=vec, payload={"agent_id": agent["id"]})])


def similar_agents(text: str, k: int = 3) -> list[tuple[int, float]]:
    [vec] = embed([text], "RETRIEVAL_QUERY")
    hits = qdrant.query_points(AGENTS, query=vec, limit=k).points
    return [(h.payload["agent_id"], h.score) for h in hits]


def _chunks(text: str) -> list[str]:
    paras, chunks, cur = [p.strip() for p in text.split("\n") if p.strip()], [], ""
    for p in paras:
        if cur and len(cur) + len(p) > CHUNK:
            chunks.append(cur)
            cur = ""
        cur = f"{cur}\n{p}".strip()
    return chunks + [cur] if cur else chunks


def add_knowledge(agent_id: int, text: str) -> int:
    chunks = _chunks(text)
    if not chunks:
        return 0
    vecs = embed(chunks, "RETRIEVAL_DOCUMENT")
    qdrant.upsert(
        KNOWLEDGE,
        [
            PointStruct(id=str(uuid.uuid4()), vector=v, payload={"agent_id": agent_id, "text": c})
            for c, v in zip(chunks, vecs)
        ],
    )
    return len(chunks)


def search_knowledge(agent_id: int, query: str, k: int = 3) -> list[str]:
    [vec] = embed([query], "RETRIEVAL_QUERY")
    hits = qdrant.query_points(
        KNOWLEDGE,
        query=vec,
        query_filter=Filter(must=[FieldCondition(key="agent_id", match=MatchValue(value=agent_id))]),
        limit=k,
    ).points
    return [h.payload["text"] for h in hits]
