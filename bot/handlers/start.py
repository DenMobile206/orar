"""/start command – whitelist gate + welcome."""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from ..keyboards import main_menu_keyboard
from ..config_loader import get as get_config
from .. import storage

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    config = get_config()
    if message.from_user.id not in config.get("whitelist", []):
        await message.reply("⛔ Nu ai acces.")
        return

    await storage.upsert_user_settings(
        message.from_user.id,
        default_group=config.get("default_group", "B"),
    )

    name = message.from_user.first_name or "utilizator"
    await message.reply(
        f"👋 Bun venit, *{name}*!\n\n"
        "Acesta este botul de pontaj pentru cursuri.\n"
        "Folosește butoanele de mai jos pentru a naviga.",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown",
    )
