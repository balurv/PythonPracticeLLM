"""MySQL storage for agents and their chat messages."""

import json
import os

import pymysql
from pymysql.cursors import DictCursor

DB = os.getenv("MYSQL_DB", "agent_hub")
JSON_FIELDS = ("skills", "mechanisms")

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS agents (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        description TEXT,
        system_prompt TEXT NOT NULL,
        skills JSON,
        requirements TEXT,
        mechanisms JSON,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS messages (
        id INT AUTO_INCREMENT PRIMARY KEY,
        agent_id INT NOT NULL,
        role VARCHAR(20) NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS tool_requests (
        id INT AUTO_INCREMENT PRIMARY KEY,
        agent_id INT NOT NULL,
        name VARCHAR(100) NOT NULL,
        issue_number INT NOT NULL,
        issue_url VARCHAR(300) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY agent_tool (agent_id, issue_number),
        FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
    )""",
]


def connect(database: str | None = DB):
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "root"),
        database=database,
        cursorclass=DictCursor,
        autocommit=True,
    )


def query(sql: str, args=()) -> list[dict]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall()


def init() -> None:
    with connect(database=None) as conn, conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB}`")
    with connect() as conn, conn.cursor() as cur:
        for stmt in SCHEMA:
            cur.execute(stmt)


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
