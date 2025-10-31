"""Handlers for the `/start` command."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message

from functions.mongodb import save_user

router = Router()

logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    """Send usage instructions for the bot when `/start` is invoked."""
    user = message.from_user
    if user is not None:
        try:
            await save_user(user.id, user.username, user.first_name)
        except Exception as exc:  # pragma: no cover - persistence errors shouldn't break /start
            logger.warning("Failed to persist user %s: %s", user.id, exc)

    await message.answer(
        "Send the account string in the format:\n"
        "<code>email|password|refresh_token|client_id</code>\n\n"
        "Only Hotmail/Outlook addresses are accepted.",
        parse_mode=ParseMode.HTML,
    )
