"""GET /gmail/status, /gmail/connect, /gmail/callback: browser sign-in for the read-only Gmail tool."""

import html

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from backend.integrations import gmail

router = APIRouter(prefix="/gmail", tags=["gmail"])


@router.get("/status")
def status():
    return {"connected": gmail.connected(), "connect_url": gmail.CONNECT_URL}


@router.get("/connect")
def connect():
    return RedirectResponse(gmail.authorization_url())


@router.get("/callback", response_class=HTMLResponse)
def callback(state: str, code: str | None = None, error: str | None = None):
    unknown = HTTPException(status_code=400, detail="Unknown or expired sign-in. Open /gmail/connect again.")
    if error or not code:
        if not gmail.forget_sign_in(state):
            raise unknown
        return HTMLResponse(f"<p>Gmail access was not granted ({html.escape(error or 'no code')}).</p>", status_code=400)
    try:
        gmail.finish_sign_in(state, code)
    except gmail.UnknownSignIn:
        raise unknown from None
    return HTMLResponse("<h3>Gmail connected (read-only).</h3><p>You can close this tab and ask your agent again.</p>")
