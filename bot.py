"""Telegram bot entrypoint that uses the Hotmail/Outlook inbox API."""

import asyncio
import html
import os
import re
from typing import Dict, Optional

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message

from Api.hotmailoutlookapi import fetch_inbox_preview

TELEGRAM_BOT_TOKEN = "8213966935:AAGzXbDk1JGlTj2FH-ihho6DP0zcXo2Dkyg"
DEFAULT_MESSAGE_COUNT = int(os.getenv("MESSAGE_COUNT", "5"))

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
        preview_text = await asyncio.to_thread(
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
    safe_preview = html.escape(preview_text)
    await message.answer(
        f"✅ Parsed credentials for {safe_email}.\n\n{safe_preview}",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
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
