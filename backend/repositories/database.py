"""MySQL connection, raw query helper and schema. Tables: agents, messages, tool_requests."""

import pymysql
from pymysql.cursors import DictCursor

from backend import config

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


def connect(database: str | None = config.MYSQL_DB):
    return pymysql.connect(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=database,
        cursorclass=DictCursor,
        autocommit=True,
    )


def query(sql: str, args=()) -> list[dict]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall()


def init() -> None:
    """Create the database and tables if missing (called at app startup)."""
    with connect(database=None) as conn, conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{config.MYSQL_DB}`")
    with connect() as conn, conn.cursor() as cur:
        for stmt in SCHEMA:
            cur.execute(stmt)
