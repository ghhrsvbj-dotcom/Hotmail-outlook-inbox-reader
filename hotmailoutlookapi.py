
import os
import imaplib
import email
from email.header import decode_header, make_header
from typing import Optional, Dict, Any
import time

import httpx  # faster drop-in for requests

# ----------------------------------------------------
# 🔧 CONFIGURATION (env vars preferred)
EMAIL = "baileykayla7933@hotmail.com"
REFRESH_TOKEN = "M.C513_BAY.0.U.-Cn!BMEvR*OMF!Zo0aywDaczaDdkMT!j25YVVOYxyiRWemUgiLv!m3kegWpxDMn1Z8HI4K7uDVeQqvyjh4ASxjf8BJA7wHqQZed!xTxdK1TblNa42QgqMCLfHYtfyuWjRD4EhIYHcxLaSgGSubQ5tvvYSnSchF9iTeWkkXpdpcUlooOPcLjhLvX5A*rRjx2wOB*I5jA5ewr9k0TDyH0lmyKzHGP9DQQzS5gJ*Kv8SC84KPlC44eE6mAnYjBkfUxvJn0qxDBP3CFvqALoF8Oh8fq8dXCTrlOAU0oa5Exd8izJ4zxIDWlpz6D43XsXtA0ESh2fNRRhDq!f1d3w4QYkodLb*FlrnPG5IDla3FpSkia6eaYukR*dqt0pmmou66EsVquDnqnDscXRDjhxyT5Fld!4$"
CLIENT_ID = "dbc8e03a-b00c-46bd-ae65-b683e7707cb0"
CLIENT_SECRET = None  # "<YOUR_CLIENT_SECRET>" if applicable
# ----------------------------------------------------

TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
IMAP_SERVER = "outlook.office365.com"

DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)
USER_AGENT = "hotmail-inbox-reader/1.0 (+https://example.local)"

def _post_form_with_retries(url: str, data: Dict[str, str], max_retries: int = 3) -> httpx.Response:
    """
    Simple retry loop for transient network failures or 5xx responses.
    """
    backoff = 0.75
    last_exc = None
    # Using a shared Client for pooling + optional HTTP/2
    with httpx.Client(http2=True, timeout=DEFAULT_TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        for attempt in range(1, max_retries + 1):
            try:
                resp = client.post(url, data=data)
                if resp.status_code >= 500:
                    # server hiccup, retry
                    raise httpx.HTTPStatusError("server error", request=resp.request, response=resp)
                return resp
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                if attempt == max_retries:
                    break
                time.sleep(backoff)
                backoff *= 2
    # If we got here, all retries failed
    if isinstance(last_exc, httpx.HTTPStatusError):
        r = last_exc.response
        raise RuntimeError(f"Token exchange failed after retries: {r.status_code} {r.text[:500]}")
    raise RuntimeError(f"Token exchange failed after retries: {last_exc!r}")

def get_access_token(refresh_token: str, client_id: str, client_secret: Optional[str] = None) -> Dict[str, Any]:
    """
    Exchange refresh token for a new access token via Microsoft v2.0 endpoint.
    """
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
    """
    Connect to Outlook IMAP using OAuth2 token.
    """
    print("Connecting to Outlook IMAP...")
    imap = imaplib.IMAP4_SSL(IMAP_SERVER)
    auth_string = f"user={email_addr}\1auth=Bearer {token}\1\1".encode("utf-8")
    imap.authenticate("XOAUTH2", lambda _: auth_string)
    print("✅ IMAP authentication successful.")
    return imap

def _decode_subject(raw_subject: Optional[str]) -> str:
    if not raw_subject:
        return "(no subject)"
    try:
        # Handles multi-part encoded headers cleanly
        return str(make_header(decode_header(raw_subject)))
    except Exception:
        # Fallback: best-effort decode first piece
        val, enc = decode_header(raw_subject)[0]
        if isinstance(val, bytes):
            return val.decode(enc or "utf-8", errors="ignore")
        return str(val)

def list_latest_messages(imap: imaplib.IMAP4_SSL, n: int = 10) -> None:
    """
    List latest n messages from inbox with subject, sender, and a text/plain snippet.
    """
    typ, _ = imap.select("INBOX")
    if typ != "OK":
        raise RuntimeError("Failed to open INBOX")

    typ, data = imap.search(None, "ALL")
    if typ != "OK":
        raise RuntimeError("Failed to search mailbox")

    msg_ids = data[0].split()
    if not msg_ids:
        print("No messages found.")
        return

    print(f"Total messages in inbox: {len(msg_ids)}")
    latest_ids = msg_ids[-n:]
    for num in reversed(latest_ids):
        typ, msg_data = imap.fetch(num, "(RFC822)")
        if typ != "OK" or not msg_data or not msg_data[0]:
            continue
        msg = email.message_from_bytes(msg_data[0][1])
        subject = _decode_subject(msg.get("Subject"))
        sender = msg.get("From", "(unknown sender)")
        print(f"\n📧 From: {sender}")
        print(f"   Subject: {subject}")

        # Find the first text/plain part
        snippet = None
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain" and part.get_content_disposition() != "attachment":
                    body = part.get_payload(decode=True)
                    if body:
                        snippet = body.decode(part.get_content_charset() or "utf-8", errors="ignore")
                        break
        else:
            if msg.get_content_type() == "text/plain":
                body = msg.get_payload(decode=True)
                if body:
                    snippet = body.decode(msg.get_content_charset() or "utf-8", errors="ignore")

        if snippet:
            print("   Body:", snippet.strip().replace("\r", " ")[:300])
        else:
            print("   Body: (no text/plain content)")

def main():
    print(f"Using email: {EMAIL}")
    print("🔄 Exchanging refresh token for access token (HTTPX)...")
    token_data = get_access_token(REFRESH_TOKEN, CLIENT_ID, CLIENT_SECRET)
    access_token = token_data.get("access_token")
    if not access_token:
        raise RuntimeError(f"No access_token returned. Full response:\n{token_data}")

    print("✅ Got access token. Connecting to IMAP...")
    imap = connect_and_authenticate(EMAIL, access_token)
    try:
        list_latest_messages(imap, n=5)
    finally:
        imap.logout()
    print("\n✅ Done.")

if __name__ == "__main__":
    main()
