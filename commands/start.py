"""Handlers for the `/start` command."""

from aiogram import Router
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router()


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    """Send usage instructions for the bot when `/start` is invoked."""
    await message.answer(
        "Send the account string in the format:\n"
        "<code>email|password|refresh_token|client_id</code>\n\n"
        "Only Hotmail/Outlook addresses are accepted.",
        parse_mode=ParseMode.HTML,
    )
