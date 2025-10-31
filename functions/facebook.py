"""Utilities for extracting OTP codes from Facebook emails."""

from __future__ import annotations

import email
import html
import imaplib
import re
from datetime import datetime
from email.message import Message
from email.utils import parsedate_to_datetime
from typing import Literal, Optional, TypedDict
from .ignored_otp import IGNORED_OTPS

_FB_CODE_WITH_PREFIX = re.compile(r"FB-(\d{5,8})\b")
_FB_CODE_STANDALONE = re.compile(r"\b(\d{5,8})\b")


class FacebookOtpResult(TypedDict, total=False):
    """Structured information about the latest Facebook OTP email."""

    status: Literal["found", "no_otp", "no_emails"]
    otp: Optional[str]
    subject: Optional[str]
    received_at: Optional[datetime]


def _extract_otp(text: str) -> Optional[str]:
    """Return the first plausible OTP code from the provided text."""
    # First, try to find codes with FB- prefix (most reliable)
    matches_with_prefix = list(_FB_CODE_WITH_PREFIX.finditer(text))
    for match in matches_with_prefix:
        candidate = match.group(1)
        if candidate not in IGNORED_OTPS:
            return candidate
    
    # Fall back to standalone numbers
    matches_standalone = list(_FB_CODE_STANDALONE.finditer(text))
    if not matches_standalone:
        return None
    
    # Look for patterns that indicate this is a confirmation code
    # Common patterns: "confirmation code:", "code:", followed by number on next line
    text_lower = text.lower()
    confirmation_keywords = [
        "confirmation code:",
        "your code:",
        "your confirmation code:",
        "here's your confirmation code:",
        "verification code:"
    ]
    
    # If we find confirmation keywords, get the first valid number after them
    for keyword in confirmation_keywords:
        keyword_pos = text_lower.find(keyword)
        if keyword_pos != -1:
            # Look for numbers after the keyword
            for match in matches_standalone:
                if match.start() > keyword_pos:
                    candidate = match.group(1)
                    if candidate not in IGNORED_OTPS:
                        return candidate
    
    # Last resort: return the longest valid standalone number
    valid_candidates = [
        match.group(1) for match in matches_standalone 
        if match.group(1) not in IGNORED_OTPS
    ]
    
    if valid_candidates:
        return max(valid_candidates, key=len)
    
    return None

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

def _get_message_date(msg: Message) -> Optional[datetime]:
    """Extract and parse the date from an email message."""
    date_header = msg.get("Date")
    if not date_header:
        return None
    
    try:
        return parsedate_to_datetime(date_header)
    except (TypeError, ValueError):
        return None

def get_latest_facebook_otp(
    imap: imaplib.IMAP4_SSL, *, max_messages: int = 20
) -> FacebookOtpResult:
    """Return the newest Facebook OTP email (if present) within the provided window."""

    status, _ = imap.select("INBOX")
    if status != "OK":
        raise RuntimeError("Failed to open INBOX")

    status, data = imap.search(None, 'FROM', '"Facebook"')
    if status != "OK" or not data or not data[0]:
        return {
            "status": "no_emails",
            "otp": None,
            "subject": None,
            "received_at": None,
        }

    message_ids = [msg_id for msg_id in data[0].split() if msg_id]
    if not message_ids:
        return {
            "status": "no_emails",
            "otp": None,
            "subject": None,
            "received_at": None,
        }

    recent_message_ids = message_ids[-max_messages:]
    latest_subject: Optional[str] = None

    for msg_id in reversed(recent_message_ids):
        status, msg_data = imap.fetch(msg_id, "(RFC822)")
        if status != "OK" or not msg_data or not msg_data[0]:
            continue

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        subject = _decode_header_value(msg.get("Subject")) or "(no subject)"
        message_date = _get_message_date(msg)

        if latest_subject is None:
            latest_subject = subject

        otp = _extract_otp(subject)
        if not otp:
            body_text = _message_to_text(msg)
            otp = _extract_otp(body_text)

        if otp:
            return {
                "status": "found",
                "otp": otp,
                "subject": subject,
                "received_at": message_date,
            }

    return {
        "status": "no_otp",
        "otp": None,
        "subject": latest_subject,
        "received_at": None,
    }
