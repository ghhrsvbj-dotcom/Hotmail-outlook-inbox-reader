"""Handlers for the `/start` command."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

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

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇧🇩 বাংলা", callback_data="lang:bn"),
                InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en"),
            ]
        ]
    )

    await message.reply(
        "🌐 Choose your language\n"
        "Please pick how you'd like to use the bot.",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "lang:bn")
async def handle_language_bangla(callback: CallbackQuery) -> None:
    """Send onboarding instructions in Bangla."""

    await callback.answer()

    bangla_text = (
        "আমাদের বটে স্বাগতম!\n"
        "আপনি এখন খুব সহজে আপনার Hotmail বা Outlook মেইল থেকে Facebook কোড পেতে পারেন —\n"
        "শুধু আপনার মেইল পাঠান, আমরা সঙ্গে সঙ্গে কোডটা দিয়ে দেব।\n\n"
        "🔐 অ্যাকাউন্ট তথ্য পাঠাতে এই ফরম্যাট ব্যবহার করুন:\n"
        "<code>email|password|refresh_token|client_id</code>\n\n"
        "শুধুমাত্র Hotmail/Outlook ঠিকানা গ্রহণ করা হবে।"
    )

    if callback.message:
        await callback.message.edit_text(bangla_text, parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "lang:en")
async def handle_language_english(callback: CallbackQuery) -> None:
    """Send onboarding instructions in English."""

    await callback.answer()

    english_text = (
        "Welcome to our bot!\n"
        "You can get your Hotmail or Outlook Facebook codes instantly —\n"
        "just send your email, and we’ll fetch the code for you.\n\n"
        "🔐 Send the account string in this format:\n"
        "<code>email|password|refresh_token|client_id</code>\n\n"
        "Only Hotmail/Outlook addresses are accepted."
    )

    if callback.message:
        await callback.message.edit_text(english_text, parse_mode=ParseMode.HTML)
