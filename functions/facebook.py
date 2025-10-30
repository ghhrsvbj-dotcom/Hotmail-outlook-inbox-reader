"""Utilities for extracting OTP codes from Facebook emails."""

from __future__ import annotations

import email
import html
import imaplib
import re
from email.message import Message
from typing import Optional

_FB_CODE_PATTERN = re.compile(r"\b(?:FB-)?(\d{4,8})\b")


def _extract_otp(text: str) -> Optional[str]:
    """Return the first plausible OTP code from the provided text."""

    matches = list(_FB_CODE_PATTERN.finditer(text))
    if not matches:
        return None

    for match in matches:
        if match.group(0).startswith("FB-"):
            return match.group(1)

    return matches[0].group(1)


def _decode_header_value(raw_value: Optional[str]) -> str:
    """Decode RFC 2047 encoded header values defensively."""

    if not raw_value:
        return ""
    try:
        from email.header import decode_header, make_header

        return str(make_header(decode_header(raw_value)))
    except Exception:  # pragma: no cover - best effort decoding
        return raw_value


def _message_to_text(msg: Message) -> str:
    """Extract a human-readable text body from an email message."""

    def _decode_payload(part: Message) -> Optional[str]:
        payload = part.get_payload(decode=True)
        if not payload:
            return None
        charset = part.get_content_charset() or "utf-8"
        try:
            return payload.decode(charset, errors="ignore")
        except (LookupError, UnicodeDecodeError):  # pragma: no cover - defensive fallback
            return payload.decode("utf-8", errors="ignore")

    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and part.get_content_disposition() != "attachment":
                text = _decode_payload(part)
                if text:
                    return text
        for part in msg.walk():
            if part.get_content_type() == "text/html" and part.get_content_disposition() != "attachment":
                text = _decode_payload(part)
                if text:
                    return html.unescape(text)
    else:
        content_type = msg.get_content_type()
        if content_type in {"text/plain", "text/html"}:
            text = _decode_payload(msg)
            if text:
                if content_type == "text/html":
                    return html.unescape(text)
                return text
    return ""


def get_latest_facebook_otp(imap: imaplib.IMAP4_SSL, *, max_messages: int = 20) -> str:
    """Return the most recent OTP code from Facebook emails within the provided window."""

    status, _ = imap.select("INBOX")
    if status != "OK":
        raise RuntimeError("Failed to open INBOX")

    status, data = imap.search(None, 'FROM', '"Facebook"')
    if status != "OK" or not data or not data[0]:
        return "No Facebook OTP emails found."

    message_ids = [msg_id for msg_id in data[0].split() if msg_id]
    if not message_ids:
        return "No Facebook OTP emails found."

    latest_subject = "(no subject)"

    for msg_id in reversed(message_ids[-max_messages:]):
        status, msg_data = imap.fetch(msg_id, "(RFC822)")
        if status != "OK" or not msg_data or not msg_data[0]:
            continue

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)
        subject = _decode_header_value(msg.get("Subject")) or "(no subject)"
        if latest_subject == "(no subject)":
            latest_subject = subject

        body_text = _message_to_text(msg)

        otp = _extract_otp(body_text) or _extract_otp(subject)
        if otp:
            return f"Latest Facebook OTP: {otp}"

    return f"Latest Facebook email found but no OTP detected. Subject: {latest_subject}"
