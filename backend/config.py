"""All settings, read once from env vars (`.env` via python-dotenv, or the shell).

Import settings from here instead of calling os.getenv in other modules. load_dotenv runs on
import, so any module that imports `backend.config` sees `.env` values. It never overrides
variables already set in the shell (e.g. GROQ_API_KEY from ~/.zshrc).
"""

import os

from dotenv import load_dotenv

load_dotenv()

# Groq LLM
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_TIMEOUT = 60  # seconds; the SDK default is 10 minutes, fail fast so the web UI doesn't hang

# MySQL
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root")
MYSQL_DB = os.getenv("MYSQL_DB", "agent_hub")

# Qdrant + Gemini embeddings
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")

# GitHub: MCP tools for agents, and the repo that receives tool-request issues
GITHUB_REPO = os.getenv("GITHUB_REPO", "balurv/PythonPracticeLLM")
# Groq's free tier allows ~8k tokens/min, so only a few GitHub MCP tools are exposed to the LLM.
MCP_TOOLS = set(
    os.getenv(
        "MCP_TOOLS",
        "get_me,list_issues,issue_read,issue_write,add_issue_comment,list_pull_requests,get_file_contents",
    ).split(",")
)

# Gmail (read-only OAuth)
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
GMAIL_TOKEN_FILE = os.getenv("GMAIL_TOKEN_FILE", "gmail_token.json")
GMAIL_REDIRECT_URI = os.getenv("GMAIL_REDIRECT_URI", "http://localhost:8000/gmail/callback")


def github_pat() -> str:
    """Read lazily so the app starts without it; only GitHub features need it."""
    return os.environ["GITHUB_PAT"]
