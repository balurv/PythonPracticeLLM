"""MySQL access for agent chat messages (the `memory` mechanism and chat history)."""

from backend.repositories.database import query


def add_message(agent_id: int, role: str, content: str) -> None:
    query("INSERT INTO messages (agent_id, role, content) VALUES (%s, %s, %s)", (agent_id, role, content))


def messages(agent_id: int) -> list[dict]:
    return query(
        "SELECT role, content, created_at FROM messages WHERE agent_id = %s ORDER BY id", (agent_id,)
    )


def recent_messages(agent_id: int, n: int = 6) -> list[dict]:
    rows = query(
        "SELECT role, content FROM messages WHERE agent_id = %s ORDER BY id DESC LIMIT %s", (agent_id, n)
    )
    return rows[::-1]
