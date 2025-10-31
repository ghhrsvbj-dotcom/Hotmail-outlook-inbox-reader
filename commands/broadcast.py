"""Handlers for the `/brd` broadcast command."""

from __future__ import annotations

import logging
from typing import List

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from functions.mongodb import get_all_user_ids

ADMIN_USER_ID = 5850931697

router = Router()

logger = logging.getLogger(__name__)


def _extract_broadcast_text(message: Message) -> str:
    """Return the text to broadcast extracted from the command message."""

    if not message.text:
        return ""

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return ""

    return parts[1].strip()


@router.message(Command("brd"))
async def handle_broadcast(message: Message) -> None:
    """Broadcast a message to all registered users (admin-only)."""

    if message.from_user is None or message.from_user.id != ADMIN_USER_ID:
        await message.answer("❌ You are not authorized to use this command.")
        return

    broadcast_text = _extract_broadcast_text(message)
    if not broadcast_text:
        await message.answer("Usage: /brd <message to broadcast>")
        return

    user_ids: List[int] = await get_all_user_ids()
    recipients = list(dict.fromkeys(user_ids))

    if not recipients:
        await message.answer("No registered users to broadcast to.")
        return

    sent = 0
    failed = 0

    for user_id in recipients:
        try:
            await message.bot.send_message(user_id, broadcast_text)
        except Exception as exc:  # pragma: no cover - runtime delivery issues
            failed += 1
            logger.warning("Failed to deliver broadcast to %s: %s", user_id, exc)
        else:
            sent += 1

    summary = f"Broadcast delivered to {sent} user(s)."
    if failed:
        summary += f" Failed to deliver to {failed} user(s)."

    await message.answer(summary)
