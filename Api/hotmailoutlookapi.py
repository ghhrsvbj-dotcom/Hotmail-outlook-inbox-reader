"""Utility functions for interacting with the Hotmail/Outlook inbox API."""

import email
import imaplib
import os
import time
from email.header import decode_header, make_header
from typing import Any, Dict, Optional

import httpx

from functions.facebook import get_latest_facebook_otp

CLIENT_SECRET = os.getenv("CLIENT_SECRET")

TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
IMAP_SERVER = "outlook.office365.com"

DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)
USER_AGENT = "hotmail-inbox-reader/1.0 (+https://example.local)"


def _post_form_with_retries(url: str, data: Dict[str, str], max_retries: int = 3) -> httpx.Response:
    """Simple retry loop for transient network failures or 5xx responses."""

    backoff = 0.75
    last_exc: Optional[Exception] = None
    with httpx.Client(http2=True, timeout=DEFAULT_TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        for attempt in range(1, max_retries + 1):
            try:
                resp = client.post(url, data=data)
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        "server error", request=resp.request, response=resp
                    )
                return resp
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:  # pragma: no cover - network handling
                last_exc = exc
                if attempt == max_retries:
                    break
                time.sleep(backoff)
                backoff *= 2

    if isinstance(last_exc, httpx.HTTPStatusError):
        response = last_exc.response
        raise RuntimeError(
            f"Token exchange failed after retries: {response.status_code} {response.text[:500]}"
        )
    raise RuntimeError(f"Token exchange failed after retries: {last_exc!r}")


def get_access_token(
    refresh_token: str, client_id: str, client_secret: Optional[str] = None
) -> Dict[str, Any]:
    """Exchange refresh token for a new access token via Microsoft v2.0 endpoint."""

    if not refresh_token or not client_id:
        raise ValueError("Missing REFRESH_TOKEN or CLIENT_ID.")
    data = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
    }
    if client_secret:
        data["client_secret"] = client_secret

    resp = _post_form_with_retries(TOKEN_URL, data)
    if not resp.is_success:
        raise RuntimeError(f"Token exchange failed: {resp.status_code} {resp.text[:500]}")
    return resp.json()


def connect_and_authenticate(email_addr: str, token: str) -> imaplib.IMAP4_SSL:
    """Connect to Outlook IMAP using OAuth2 token."""

    imap = imaplib.IMAP4_SSL(IMAP_SERVER)
    auth_string = f"user={email_addr}\1auth=Bearer {token}\1\1".encode("utf-8")
    imap.authenticate("XOAUTH2", lambda _: auth_string)
    return imap


def _decode_subject(raw_subject: Optional[str]) -> str:
    if not raw_subject:
        return "(no subject)"
    try:
        return str(make_header(decode_header(raw_subject)))
    except Exception:  # pragma: no cover - defensive fallback
        val, enc = decode_header(raw_subject)[0]
        if isinstance(val, bytes):
            return val.decode(enc or "utf-8", errors="ignore")
        return str(val)


def list_latest_messages(imap: imaplib.IMAP4_SSL, n: int = 10) -> str:
    """List latest n messages from inbox with subject, sender, and a text/plain snippet."""

    typ, _ = imap.select("INBOX")
    if typ != "OK":
        raise RuntimeError("Failed to open INBOX")

    typ, data = imap.search(None, "ALL")
    if typ != "OK":
        raise RuntimeError("Failed to search mailbox")

    msg_ids = data[0].split()
    if not msg_ids:
        return "No messages found."

    lines = [f"Total messages in inbox: {len(msg_ids)}"]
    latest_ids = msg_ids[-n:]
    for num in reversed(latest_ids):
        typ, msg_data = imap.fetch(num, "(RFC822)")
        if typ != "OK" or not msg_data or not msg_data[0]:
            continue
        msg = email.message_from_bytes(msg_data[0][1])
        subject = _decode_subject(msg.get("Subject"))
        sender = msg.get("From", "(unknown sender)")

        snippet = None
        if msg.is_multipart():
            for part in msg.walk():
                if (
                    part.get_content_type() == "text/plain"
                    and part.get_content_disposition() != "attachment"
                ):
                    body = part.get_payload(decode=True)
                    if body:
                        snippet = body.decode(part.get_content_charset() or "utf-8", errors="ignore")
                        break
        else:
            if msg.get_content_type() == "text/plain":
                body = msg.get_payload(decode=True)
                if body:
                    snippet = body.decode(msg.get_content_charset() or "utf-8", errors="ignore")

        snippet_text = (
            snippet.strip().replace("\r", " ")[:300] if snippet else "(no text/plain content)"
        )
        lines.append(f"\n📧 From: {sender}\n   Subject: {subject}\n   Body: {snippet_text}")

    return "\n".join(lines)


def fetch_inbox_preview(
    email_addr: str, refresh_token: str, client_id: str, *, message_count: int
) -> str:
    """Fetch the most recent Facebook OTP message for the provided inbox."""

    del message_count

    token_data = get_access_token(refresh_token, client_id, CLIENT_SECRET)
    access_token = token_data.get("access_token")
    if not access_token:
        raise RuntimeError(f"No access_token returned. Full response:\n{token_data}")

    imap = connect_and_authenticate(email_addr, access_token)
    try:
        inbox_text = get_latest_facebook_otp(imap)
    finally:
        imap.logout()

    return inbox_text
