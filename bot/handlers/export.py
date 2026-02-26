"""Export Excel attendance report."""
from __future__ import annotations

import io

from aiogram import F, Router
from aiogram.types import BufferedInputFile, Message

from .. import storage
from ..config_loader import get as get_config
from ..export_excel import generate_excel

router = Router()


def _check(user_id: int) -> bool:
    return user_id in get_config().get("whitelist", [])


@router.message(F.text == "Export Excel")
async def export_handler(message: Message) -> None:
    if not _check(message.from_user.id):
        await message.reply("⛔ Nu ai acces.")
        return

    wait_msg = await message.reply("⏳ Generez raportul Excel…")

    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or str(user_id)

    all_attendance = await storage.get_all_attendance_log(user_id)
    stats_raw = await storage.get_attendance_stats(user_id)

    if not all_attendance:
        await wait_msg.edit_text("📭 Nu există date de exportat.")
        return

    xlsx_bytes = generate_excel(user_id, username, all_attendance, stats_raw)

    file = BufferedInputFile(
        xlsx_bytes,
        filename=f"prezenta_{username}.xlsx",
    )
    await message.reply_document(
        document=file,
        caption=f"📊 Raport prezență pentru *{username}*",
        parse_mode="Markdown",
    )
    await wait_msg.delete()
