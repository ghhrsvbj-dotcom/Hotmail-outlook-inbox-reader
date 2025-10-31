"""Utilities for scraping Gmail with Playwright.

This module exposes a helper function that logs into Gmail using a fixed
password and returns a short summary of the inbox contents.  It is primarily
intended to be used by the Telegram bot defined in :mod:`bot`.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List

from playwright.sync_api import Page, TimeoutError, sync_playwright

# Gmail credentials.  The password is fixed while the email is provided by the
# end user through the Telegram bot.
PASSWORD = "Nxnt3979"

URL = (
    "https://accounts.google.com/v3/signin/identifier?"
    "continue=https%3A%2F%2Fmail.google.com%2Fmail%2F&"
    "dsh=S1157872587%3A1760592988268952&ec=asw-gmail-globalnav-signin&"
    "flowEntry=AccountChooser&flowName=GlifWebSignIn&service=mail"
)


def _click_optional_confirm(page: Page) -> bool:
    """Attempt to click any optional confirmation prompt.

    Returns ``True`` when a confirmation element was located and clicked.
    """

    selectors = [
        "input#confirm",
        'input[name="confirm"]',
        'input[type="submit"][value="আমি বুঝেছি"]',
        'input[type="submit"]',
    ]
    for selector in selectors:
        try:
            element = page.wait_for_selector(selector, timeout=3000)
        except TimeoutError:
            continue

        if not element:
            continue

        try:
            if element.is_enabled() and element.is_visible():
                element.click()
                return True
        except Exception:
            # Fall back to an evaluation click when direct interaction fails.
            page.evaluate("(el) => el.click()", element)
            return True
    return False


def _safe_inner_text(element) -> str:
    try:
        return element.inner_text().strip()
    except Exception:
        return ""


def fetch_inbox_summary(
    email: str,
    *,
    password: str = PASSWORD,
    max_rows: int = 10,
    headless: bool = True,
) -> Dict[str, Any]:
    """Log into Gmail and collect an overview of the inbox.

    Parameters
    ----------
    email:
        The Gmail address to authenticate with.  The password is fixed and
        provided via :data:`PASSWORD`.
    password:
        Optionally override the password for the login attempt.
    max_rows:
        The maximum number of inbox rows to capture.
    headless:
        Controls whether Playwright launches the Chromium browser in headless
        mode.

    Returns
    -------
    dict
        A dictionary with the following keys:

        ``emails``
            A list of dictionaries describing the inbox rows.
        ``first_body``
            The body text of the first email (if available).
        ``confirm_clicked``
            ``True`` if a confirmation dialog was detected and dismissed.
        ``errors``
            A list of error messages encountered during the scraping process.
    """

    start_time = time.perf_counter()

    result: Dict[str, Any] = {
        "emails": [],
        "first_body": "",
        "confirm_clicked": False,
        "errors": [],
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(viewport={"width": 1200, "height": 800})
        page = context.new_page()

        try:
            page.goto(URL, timeout=60000)
            page.fill("input#identifierId", email)
            page.click("#identifierNext")

            try:
                page.wait_for_selector('input[name="Passwd"]', timeout=20000)
            except TimeoutError:
                result["errors"].append("Password field not available; login may be blocked.")
                return result

            page.fill('input[name="Passwd"]', password)
            page.click("#passwordNext")

            try:
                result["confirm_clicked"] = _click_optional_confirm(page)
                if result["confirm_clicked"]:
                    page.wait_for_timeout(1500)
            except Exception as exc:  # pragma: no cover - best effort to continue
                result["errors"].append(f"Failed to interact with confirm dialog: {exc}")

            try:
                page.wait_for_url(lambda url: "mail.google.com" in url, timeout=60000)
            except TimeoutError:
                result["errors"].append(f"Timed out waiting for Gmail to load (last URL: {page.url}).")
                return result

            try:
                page.wait_for_selector("tr.zA", timeout=30000)
            except TimeoutError:
                result["errors"].append("Inbox rows not detected; the UI may have changed.")
                return result

            rows = page.query_selector_all("tr.zA")
            for index, row in enumerate(rows[:max_rows]):
                try:
                    sender_el = row.query_selector("span.yP") or row.query_selector("span.zF")
                    subject_el = row.query_selector("span.bog")
                    snippet_el = row.query_selector("span.y2") or row.query_selector("div.y6")
                    time_el = row.query_selector("td.xW span") or row.query_selector("span.g3")
                    result["emails"].append(
                        {
                            "index": index,
                            "sender": _safe_inner_text(sender_el) if sender_el else "",
                            "subject": _safe_inner_text(subject_el) if subject_el else "",
                            "snippet": _safe_inner_text(snippet_el) if snippet_el else "",
                            "time": _safe_inner_text(time_el) if time_el else "",
                        }
                    )
                except Exception as exc:
                    result["errors"].append(f"Failed to parse inbox row {index}: {exc}")

            if rows:
                try:
                    rows[0].click()
                    page.wait_for_selector("div.a3s", timeout=10000)
                    body_el = page.query_selector("div.a3s") or page.query_selector("div.ii.gt")
                    if body_el:
                        result["first_body"] = _safe_inner_text(body_el)
                except TimeoutError:
                    result["errors"].append("Timed out waiting for the first email body.")
                except Exception as exc:
                    result["errors"].append(f"Failed to open the first email: {exc}")
        finally:
            context.close()
            browser.close()

    result["duration"] = time.perf_counter() - start_time

    return result


def format_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Extract Facebook confirmation codes from the inbox summary.

    The returned dictionary contains three keys:

    ``codes``
        A list of confirmation codes sorted by discovery order and with
        duplicates removed.
    ``duration``
        The elapsed scraping time if it was reported in ``summary``.
    ``errors``
        Any warning messages gathered during scraping.
    """

    otp_pattern = re.compile(r"\b(\d{5,9})\b")
    facebook_keywords = ("facebook", "meta")
    confirmation_keywords = ("confirmation code",)

    def is_facebook_confirmation(email_info: Dict[str, Any]) -> bool:
        combined = " ".join(
            [
                email_info.get("sender", ""),
                email_info.get("subject", ""),
                email_info.get("snippet", ""),
            ]
        ).lower()
        return any(keyword in combined for keyword in facebook_keywords) and any(
            keyword in combined for keyword in confirmation_keywords
        )

    ignored_codes = {"94025"}

    def extract_codes(text: str) -> List[str]:
        return [match.group(1) for match in otp_pattern.finditer(text or "")]

    codes: List[str] = []
    seen = set()

    for email_info in summary.get("emails", []):
        if not is_facebook_confirmation(email_info):
            continue

        for source in (email_info.get("subject"), email_info.get("snippet")):
            for code in extract_codes(source or ""):
                if code in ignored_codes:
                    continue
                if code not in seen:
                    seen.add(code)
                    codes.append(code)

    if summary.get("first_body"):
        for code in extract_codes(summary["first_body"]):
            if code in ignored_codes:
                continue
            if code not in seen:
                seen.add(code)
                codes.append(code)

    return {
        "codes": codes,
        "duration": summary.get("duration"),
        "errors": list(summary.get("errors", [])),
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python edu.py <email>")
        sys.exit(1)

    email_address = sys.argv[1]
    summary = fetch_inbox_summary(email_address, headless=False)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
