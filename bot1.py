"""Telegram bot entry-point built with the aiogram framework."""

from __future__ import annotations

import asyncio
import html
import os
import re
from concurrent.futures import ThreadPoolExecutor

from aiogram import Bot, Dispatcher
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from edu import fetch_inbox_summary, format_summary

TELEGRAM_TOKEN = "8296222155:AAGC5W0jhW9baltfaV9YWkHql2bpkVisxGI"
if not TELEGRAM_TOKEN:
    raise RuntimeError("The TELEGRAM_BOT_TOKEN environment variable must be set.")

bot = Bot(TELEGRAM_TOKEN)
dp = Dispatcher()
executor = ThreadPoolExecutor(max_workers=2)

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dp.message(Command(commands={"start", "help"}))
async def send_welcome(message: Message) -> None:
    await message.answer(
        (
            "Send me the Gmail address you would like to inspect.\n"
            "The password is fixed on the server, so only provide the email address."
        )
    )


@dp.message()
async def handle_email(message: Message) -> None:
    email = (message.text or "").strip()
    if not EMAIL_REGEX.match(email):
        await message.reply("Please send a valid email address.")
        return

    chat_id = message.chat.id
    await bot.send_chat_action(chat_id, ChatAction.TYPING)

    loop = asyncio.get_running_loop()

    try:
        summary = await loop.run_in_executor(executor, fetch_inbox_summary, email)
        summary_data = format_summary(summary)
        codes = summary_data.get("codes", [])
        duration = summary_data.get("duration")
        errors = summary_data.get("errors", [])

        if codes:
            code_lines = "\n".join(
                f"Facebook confirmation code : <code>{html.escape(str(code))}</code>"
                for code in codes
            )
            time_text = f"Time : {duration:.2f}s" if duration is not None else "Time : N/A"
            message_text = (
                "✨OTP FOUND  ✨\n\n"
                f"{code_lines}\n\n"
                f"{html.escape(time_text)}"
            )
            await message.answer(message_text, parse_mode=ParseMode.HTML)
        elif errors:
            warnings = "\n".join(f"- {error}" for error in errors)
            await message.answer(
                "No Facebook confirmation codes were found.\n\n"
                f"Warnings:\n{warnings}"
            )
        else:
            await message.answer("No Facebook confirmation codes were found.")
    except Exception as exc:  # pragma: no cover - network/Playwright errors
        await message.answer(f"An error occurred while fetching the inbox: {exc}")


if __name__ == "__main__":
    async def main() -> None:
        await dp.start_polling(bot)

    asyncio.run(main())
