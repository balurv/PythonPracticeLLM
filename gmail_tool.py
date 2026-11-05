"""Read-only Gmail tools for agents with the `gmail` mechanism.

One-time sign-in (opens a browser, saves a refresh token to GMAIL_TOKEN_FILE):
    uv run python gmail_tool.py auth
Then try it:
    uv run python gmail_tool.py search "from:amazon receipt newer_than:30d"

Env: GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET (Google Cloud OAuth client, "Desktop app" type,
Gmail API enabled), optional GMAIL_TOKEN_FILE (default gmail_token.json, git-ignored).
"""

import base64
import html
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]  # read-only: agents can never send or delete
TOKEN_FILE = Path(os.getenv("GMAIL_TOKEN_FILE", "gmail_token.json"))
MAX_RESULTS = 20
MAX_BODY_CHARS = 3000  # keep tool results small for Groq's free-tier TPM cap


def _client_config() -> dict:
    client_id, secret = os.getenv("GMAIL_CLIENT_ID"), os.getenv("GMAIL_CLIENT_SECRET")
    if not client_id or not secret:
        raise RuntimeError("Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET (Google OAuth Desktop client).")
    return {"installed": {
        "client_id": client_id,
        "client_secret": secret,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }}


def authorize() -> None:
    """Browser sign-in; stores the refresh token so the server never needs a browser."""
    creds = InstalledAppFlow.from_client_config(_client_config(), SCOPES).run_local_server(port=0)
    TOKEN_FILE.write_text(creds.to_json())
    TOKEN_FILE.chmod(0o600)
    print(f"Saved Gmail token to {TOKEN_FILE}")


def _service():
    if not TOKEN_FILE.exists():
        raise RuntimeError(
            "The Gmail tool is installed but not signed in yet (one-time setup, not a missing tool). "
            "Tell the user to run `uv run python gmail_tool.py auth` once, then ask again."
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds.valid:
        creds.refresh(Request())  # access tokens last ~1h; the refresh token renews them
        TOKEN_FILE.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _header(msg: dict, name: str) -> str:
    return next((h["value"] for h in msg["payload"].get("headers", []) if h["name"].lower() == name), "")


def _body(part: dict) -> str:
    """Prefer text/plain anywhere in the MIME tree; fall back to tag-stripped HTML."""
    plain, rich = [], []

    def walk(p: dict) -> None:
        data = p.get("body", {}).get("data")
        if data:
            text = base64.urlsafe_b64decode(data).decode("utf-8", "replace")
            (plain if p.get("mimeType") == "text/plain" else rich if p.get("mimeType") == "text/html" else []).append(text)
        for sub in p.get("parts", []):
            walk(sub)

    walk(part)
    if plain:
        return "\n".join(plain)
    text = re.sub(r"<(script|style).*?</\1>", "", "\n".join(rich), flags=re.S | re.I)
    return html.unescape(re.sub(r"<[^>]+>", " ", text))


def search_emails(query: str, max_results: int = 10) -> str:
    gmail = _service()
    found = gmail.users().messages().list(
        userId="me", q=query, maxResults=min(max(int(max_results), 1), MAX_RESULTS)
    ).execute().get("messages", [])
    if not found:
        return "No emails match that query."
    lines = []
    for m in found:
        msg = gmail.users().messages().get(
            userId="me", id=m["id"], format="metadata", metadataHeaders=["From", "Subject", "Date"]
        ).execute()
        lines.append(
            f"id={m['id']} | {_header(msg, 'date')} | from: {_header(msg, 'from')} | "
            f"subject: {_header(msg, 'subject')} | {msg.get('snippet', '')[:150]}"
        )
    return "\n".join(lines)


def read_email(message_id: str) -> str:
    msg = _service().users().messages().get(userId="me", id=message_id, format="full").execute()
    body = re.sub(r"\n\s*\n+", "\n\n", _body(msg["payload"])).strip()
    if len(body) > MAX_BODY_CHARS:
        body = body[:MAX_BODY_CHARS] + "\n…(truncated)"
    return (
        f"From: {_header(msg, 'from')}\nTo: {_header(msg, 'to')}\nDate: {_header(msg, 'date')}\n"
        f"Subject: {_header(msg, 'subject')}\n\n{body}"
    )


# name -> (function spec, python fn), the LocalTools format mcp_client.run expects.
TOOLS = {
    "search_emails": ({
        "name": "search_emails",
        "description": "Search the user's Gmail (read-only). Returns id, date, sender, subject and a "
        "snippet per email. Use Gmail search syntax, e.g. 'receipt newer_than:30d' or 'from:uber'.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Gmail search query"},
                "max_results": {"type": "integer", "description": f"1-{MAX_RESULTS}, default 10"},
            },
            "required": ["query"],
        },
    }, search_emails),
    "read_email": ({
        "name": "read_email",
        "description": "Read one email's headers and text body by id (from search_emails).",
        "parameters": {
            "type": "object",
            "properties": {"message_id": {"type": "string"}},
            "required": ["message_id"],
        },
    }, read_email),
}


if __name__ == "__main__":
    cmd, *rest = sys.argv[1:] or ["auth"]
    if cmd == "auth":
        authorize()
    elif cmd == "search":
        print(search_emails(" ".join(rest) or "newer_than:7d", 5))
    elif cmd == "read":
        print(read_email(rest[0]))
    else:
        sys.exit("usage: gmail_tool.py auth | search <query> | read <message_id>")
