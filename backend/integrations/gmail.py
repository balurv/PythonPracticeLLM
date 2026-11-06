"""Read-only Gmail tools for agents with the `gmail` mechanism, plus the OAuth flow behind them.

Connecting Gmail happens in the browser: when an agent needs Gmail and it isn't connected,
the tool error gives the agent a link to GET /gmail/connect (controllers/gmail_controller.py).
That redirects to Google's consent page, and Google sends the user back to /gmail/callback,
which saves a refresh token to GMAIL_TOKEN_FILE.
CLI: `uv run python -m backend.integrations.gmail search "receipt"`.

Env: GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET (Google Cloud OAuth "Web application" client, Gmail API
enabled, with GMAIL_REDIRECT_URI added to its Authorized redirect URIs),
optional GMAIL_TOKEN_FILE (default gmail_token.json, git-ignored) and GMAIL_REDIRECT_URI
(default http://localhost:8000/gmail/callback).
"""

import base64
import html
import re
import sys
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from backend import config

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]  # read-only: agents can never send or delete
TOKEN_FILE = Path(config.GMAIL_TOKEN_FILE)
REDIRECT_URI = config.GMAIL_REDIRECT_URI
CONNECT_URL = REDIRECT_URI.rsplit("/", 1)[0] + "/connect"
MAX_RESULTS = 20
MAX_BODY_CHARS = 3000  # keep tool results small for Groq's free-tier TPM cap

_pending: dict[str, str] = {}  # OAuth state -> PKCE code verifier, for sign-ins in progress


class NotConnected(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "Gmail isn't connected yet (a one-time permission, not a missing tool). Give the user this "
            f"link to allow read-only access, then ask them to repeat their request: {CONNECT_URL}"
        )


class UnknownSignIn(ValueError):
    """The OAuth callback's state isn't one we issued (expired, reused, or the server reloaded)."""


def _flow(**kwargs) -> Flow:
    client_id, secret = config.GMAIL_CLIENT_ID, config.GMAIL_CLIENT_SECRET
    if not client_id or not secret:
        raise RuntimeError("Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET (Google OAuth client).")
    config_ = {"web": {  # Web application client; REDIRECT_URI must be in its Authorized redirect URIs
        "client_id": client_id,
        "client_secret": secret,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }}
    return Flow.from_client_config(config_, SCOPES, redirect_uri=REDIRECT_URI, **kwargs)


def connected() -> bool:
    return TOKEN_FILE.exists()


def authorization_url() -> str:
    """Start a sign-in: return Google's consent URL and remember its PKCE verifier."""
    flow = _flow()
    # offline + consent so Google returns a refresh token every time
    url, state = flow.authorization_url(access_type="offline", prompt="consent")
    _pending[state] = flow.code_verifier
    return url


def finish_sign_in(state: str, code: str) -> None:
    """Exchange the callback's code for tokens and save them to TOKEN_FILE."""
    verifier = _pending.pop(state, None)
    if verifier is None:
        raise UnknownSignIn()
    flow = _flow(state=state, code_verifier=verifier)
    flow.fetch_token(code=code)
    TOKEN_FILE.write_text(flow.credentials.to_json())
    TOKEN_FILE.chmod(0o600)


def forget_sign_in(state: str) -> bool:
    """Drop a pending sign-in (user denied access). Returns False if the state was unknown."""
    return _pending.pop(state, None) is not None


def _service():
    if not connected():
        raise NotConnected()
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds.valid:
        try:
            creds.refresh(Request())  # access tokens last ~1h; the refresh token renews them
        except RefreshError:  # access revoked or token expired: ask the user to connect again
            TOKEN_FILE.unlink(missing_ok=True)
            raise NotConnected() from None
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


def connect_gmail() -> str:
    if connected():
        return "Gmail is already connected (read-only). Use search_emails / read_email."
    return (
        f"Give the user this link to connect Gmail (read-only, via Google's own sign-in page): {CONNECT_URL} "
        "They pick the account there; then ask them to repeat their request."
    )


# name -> (function spec, python fn), the LocalTools format mcp_client.run expects.
TOOLS = {
    "connect_gmail": ({
        "name": "connect_gmail",
        "description": "Check whether the user's Gmail is connected, or get the link the user opens to "
        "connect it (Google sign-in, read-only). Call this when the user asks to connect Gmail or an account.",
        "parameters": {"type": "object", "properties": {}},
    }, connect_gmail),
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
    cmd, *rest = sys.argv[1:] or ["search"]
    if cmd == "search":
        print(search_emails(" ".join(rest) or "newer_than:7d", 5))
    elif cmd == "read":
        print(read_email(rest[0]))
    else:
        sys.exit("usage: python -m backend.integrations.gmail search <query> | read <message_id>  (connect Gmail at /gmail/connect)")
