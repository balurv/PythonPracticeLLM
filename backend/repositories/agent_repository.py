"""MySQL access for agents and the tool requests (GitHub issues) linked to them."""

import json

from backend.repositories.database import connect, query

JSON_FIELDS = ("skills", "mechanisms")


def _decode(row: dict) -> dict:
    for f in JSON_FIELDS:
        row[f] = json.loads(row[f]) if row.get(f) else []
    row["tool_requests"] = tool_requests(row["id"])
    return row


def create_agent(name, description, system_prompt, skills, requirements, mechanisms) -> dict:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO agents (name, description, system_prompt, skills, requirements, mechanisms)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            (name, description, system_prompt, json.dumps(skills), requirements, json.dumps(mechanisms)),
        )
        return get_agent(cur.lastrowid)


def get_agent(agent_id: int) -> dict | None:
    rows = query("SELECT * FROM agents WHERE id = %s", (agent_id,))
    return _decode(rows[0]) if rows else None


def list_agents() -> list[dict]:
    return [_decode(r) for r in query("SELECT * FROM agents ORDER BY id DESC")]


def update_mechanisms(agent_id: int, mechanisms: list[str]) -> None:
    query("UPDATE agents SET mechanisms = %s WHERE id = %s", (json.dumps(mechanisms), agent_id))


def add_tool_request(agent_id: int, name: str, issue_number: int, issue_url: str) -> None:
    query(
        "INSERT IGNORE INTO tool_requests (agent_id, name, issue_number, issue_url) VALUES (%s, %s, %s, %s)",
        (agent_id, name, issue_number, issue_url),
    )


def tool_requests(agent_id: int) -> list[dict]:
    return query(
        "SELECT name, issue_number, issue_url FROM tool_requests WHERE agent_id = %s ORDER BY id", (agent_id,)
    )
