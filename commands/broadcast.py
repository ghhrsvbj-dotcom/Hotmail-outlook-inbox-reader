"""Handlers for the `/brd` broadcast command."""

from __future__ import annotations

import logging
from typing import List

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from functions.mongodb import get_all_user_ids

ADMIN_USER_ID = 5850931697

router = Router()

logger = logging.getLogger(__name__)

CONFIRM_PREFIX = "brd:confirm:"
CANCEL_PREFIX = "brd:cancel:"


def _is_admin(message: Message | CallbackQuery) -> bool:
    """Return ``True`` if the update was triggered by the configured admin."""

    if message.from_user is None:
        return False

    return message.from_user.id == ADMIN_USER_ID


@router.message(Command("brd"))
async def handle_broadcast(message: Message) -> None:
    """Start the broadcast confirmation flow (admin-only)."""

    if not _is_admin(message):
        await message.answer("❌ You are not authorized to use this command.")
        return

    if message.reply_to_message is None:
        await message.answer(
            "Please reply to the message you want to broadcast and send /brd again."
        )
        return

    source_chat_id = message.reply_to_message.chat.id
    source_message_id = message.reply_to_message.message_id

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Confirm",
                    callback_data=f"{CONFIRM_PREFIX}{source_chat_id}:{source_message_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Cancel",
                    callback_data=f"{CANCEL_PREFIX}{source_chat_id}:{source_message_id}",
                )
            ],
        ]
    )

    await message.answer(
        "Send this message to all users?",
        reply_markup=keyboard,
    )


async def _broadcast_message(bot: Bot, from_chat_id: int, message_id: int) -> tuple[int, int, int]:
    """Broadcast the referenced message and return broadcast statistics."""

    user_ids: List[int] = await get_all_user_ids()
    recipients = list(dict.fromkeys(user_ids))

    total = len(recipients)
    sent = 0
    failed = 0

    for user_id in recipients:
        try:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=from_chat_id,
                message_id=message_id,
            )
        except Exception as exc:  # pragma: no cover - runtime delivery issues
            failed += 1
            logger.warning("Failed to deliver broadcast to %s: %s", user_id, exc)
        else:
            sent += 1

    return total, sent, failed


def _parse_callback_payload(callback_data: str, expected_prefix: str) -> tuple[int, int] | None:
    """Extract ``(chat_id, message_id)`` from callback data if it matches the prefix."""

    if not callback_data.startswith(expected_prefix):
        return None

    payload = callback_data[len(expected_prefix) :]
    try:
        chat_id_str, message_id_str = payload.split(":", maxsplit=1)
    except ValueError:
        return None

    try:
        return int(chat_id_str), int(message_id_str)
    except ValueError:
        return None


@router.callback_query(F.data.startswith(CONFIRM_PREFIX))
async def confirm_broadcast(callback_query: CallbackQuery) -> None:
    """Handle confirmation of the broadcast request."""

    if not _is_admin(callback_query):
        await callback_query.answer("Not authorized.", show_alert=True)
        return

    payload = _parse_callback_payload(callback_query.data or "", CONFIRM_PREFIX)
    if payload is None:
        await callback_query.answer("Invalid confirmation payload.", show_alert=True)
        return

    chat_id, message_id = payload

    await callback_query.answer("Broadcast started…")

    total, sent, failed = await _broadcast_message(callback_query.bot, chat_id, message_id)

    if total == 0:
        await callback_query.message.edit_text("No registered users to broadcast to.")
        return

    summary = (
        "Broadcast complete.\n"
        f"Total users: {total}\n"
        f"Successful: {sent}\n"
        f"Unsuccessful: {failed}"
    )

    await callback_query.message.edit_text(summary)


@router.callback_query(F.data.startswith(CANCEL_PREFIX))
async def cancel_broadcast(callback_query: CallbackQuery) -> None:
    """Handle cancellation of the broadcast request."""

    if not _is_admin(callback_query):
        await callback_query.answer("Not authorized.", show_alert=True)
        return

    await callback_query.answer("Broadcast cancelled.")
    await callback_query.message.edit_text("Broadcast cancelled.")
