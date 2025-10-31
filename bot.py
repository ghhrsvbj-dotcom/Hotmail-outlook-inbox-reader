"""Telegram bot entrypoint that uses the Hotmail/Outlook inbox API."""

import asyncio
import html
import os
import re
from datetime import datetime, timezone
from typing import Dict, Optional

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from Api.hotmailoutlookapi import fetch_inbox_preview

TELEGRAM_BOT_TOKEN = "8213966935:AAGzXbDk1JGlTj2FH-ihho6DP0zcXo2Dkyg"
DEFAULT_MESSAGE_COUNT = int(os.getenv("MESSAGE_COUNT", "40"))

DATA_PATTERN = re.compile(
    r"(?P<email>[A-Za-z0-9._%+-]+@(hotmail|outlook)\.[A-Za-z0-9.-]+)\|"
    r"(?P<password>[^|]*)\|"
    r"(?P<refresh>M\.[^|]+)\|"
    r"(?P<client>[0-9a-fA-F-]{36})"
)

router = Router()


def _parse_credentials(raw: Optional[str]) -> Optional[Dict[str, str]]:
    if not raw:
        return None
    match = DATA_PATTERN.search(raw.strip())
    if not match:
        return None
    return {
        "email": match.group("email"),
        "refresh": match.group("refresh"),
        "client": match.group("client"),
    }


def _format_timestamp(value: Optional[datetime]) -> str:
    if not value:
        return "Unknown"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    await message.answer(
        "Send the account string in the format:\n"
        "<code>email|password|refresh_token|client_id</code>\n\n"
        "Only Hotmail/Outlook addresses are accepted.",
        parse_mode=ParseMode.HTML,
    )


@router.message(F.text)
async def handle_credentials(message: Message) -> None:
    creds = _parse_credentials(message.text)
    if not creds:
        await message.answer(
            "❌ Unable to parse credentials. Ensure the format is "
            "email|password|refresh_token|client_id and the email is Hotmail/Outlook."
        )
        return

    try:
        preview_data = await asyncio.to_thread(
            fetch_inbox_preview,
            creds["email"],
            creds["refresh"],
            creds["client"],
            message_count=DEFAULT_MESSAGE_COUNT,
        )
    except Exception as exc:  # noqa: BLE001 - deliver full context to the user
        await message.answer(f"❌ Error: {exc}")
        return

    safe_email = html.escape(creds["email"])
    status = preview_data.get("status")
    if status != "found" or not preview_data.get("otp"):
        if status == "no_otp":
            subject = html.escape(preview_data.get("subject") or "(no subject)")
            await message.answer(
                "⚠️ Latest Facebook email found but no OTP detected.\n"
                f"Subject: {subject}",
                disable_web_page_preview=True,
            )
        else:
            await message.answer(
                "❌ No Facebook OTP emails found.",
                disable_web_page_preview=True,
            )
        return

    otp = preview_data["otp"]
    received_at = preview_data.get("received_at")
    elapsed_seconds = preview_data.get("elapsed_seconds", 0.0)
    formatted_time = _format_timestamp(received_at)
    elapsed_text = f"{elapsed_seconds:.2f} seconds"

    message_text = (
        "✨FACEBOOK OTP FOUND ✨\n\n"
        f"✉️ Email : {safe_email}\n"
        f"🔐 OTP : <code>{html.escape(otp)}</code>\n"
        f"🕒 Time : {html.escape(formatted_time)}\n"
        f"⏱️ Time taken : {elapsed_text}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Copy OTP",
                    copy_text={"text": otp},
                )
            ]
        ]
    )

    await message.answer(
        message_text,
        disable_web_page_preview=True,
        reply_markup=keyboard,
    )


async def run_bot() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is required to run the bot.")

    bot = Bot(
        token=TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run_bot())
