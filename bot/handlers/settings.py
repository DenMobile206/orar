"""Settings handler: change default group and week override."""
from __future__ import annotations

from typing import Optional

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .. import storage
from ..config_loader import get as get_config
from ..keyboards import SettingsCallback

router = Router()


def _check(user_id: int) -> bool:
    return user_id in get_config().get("whitelist", [])


def _settings_keyboard(group: str, week_override: Optional[str]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    # Group buttons
    for g in ("A", "B"):
        prefix = "✔ " if group == g else ""
        b.button(
            text=f"{prefix}Grupa {g}",
            callback_data=SettingsCallback(action="group", value=g),
        )
    b.adjust(2)

    # Week override buttons
    overrides = [("auto", "🔄 Auto"), ("impar", "Săpt. IMPARĂ"), ("par", "Săpt. PARĂ")]
    current_ov = week_override or "auto"
    for ov, label in overrides:
        prefix = "✔ " if current_ov == ov else ""
        b.button(
            text=f"{prefix}{label}",
            callback_data=SettingsCallback(action="week", value=ov),
        )
    b.adjust(3)
    return b.as_markup()


def _settings_text(group: str, week_override: Optional[str]) -> str:
    wt_label = {None: "Auto (detectat)", "impar": "IMPARĂ (forțat)", "par": "PARĂ (forțat)"}.get(
        week_override, week_override
    )
    return (
        "⚙️ *Setări*\n\n"
        f"Grupă implicită: *{group}*\n"
        f"Tip săptămână: *{wt_label}*\n\n"
        "Modifică:"
    )


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

@router.message(F.text == "Setări")
async def settings_handler(message: Message) -> None:
    if not _check(message.from_user.id):
        await message.reply("⛔ Nu ai acces.")
        return

    s = await storage.get_user_settings(message.from_user.id)
    if not s:
        cfg = get_config()
        group, week_override = cfg.get("default_group", "B"), None
    else:
        group = s.get("default_group", "B")
        week_override = s.get("week_override")

    await message.reply(
        _settings_text(group, week_override),
        reply_markup=_settings_keyboard(group, week_override),
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# Callback: change group
# ---------------------------------------------------------------------------

@router.callback_query(SettingsCallback.filter(F.action == "group"))
async def settings_group(
    callback: CallbackQuery, callback_data: SettingsCallback
) -> None:
    if not _check(callback.from_user.id):
        await callback.answer("⛔ Nu ai acces.", show_alert=True)
        return

    new_group = callback_data.value
    await storage.upsert_user_settings(callback.from_user.id, default_group=new_group)

    s = await storage.get_user_settings(callback.from_user.id)
    week_override = s.get("week_override") if s else None

    await callback.message.edit_text(
        _settings_text(new_group, week_override),
        reply_markup=_settings_keyboard(new_group, week_override),
        parse_mode="Markdown",
    )
    await callback.answer(f"Grupă schimbată la {new_group}")


# ---------------------------------------------------------------------------
# Callback: change week override
# ---------------------------------------------------------------------------

@router.callback_query(SettingsCallback.filter(F.action == "week"))
async def settings_week(
    callback: CallbackQuery, callback_data: SettingsCallback
) -> None:
    if not _check(callback.from_user.id):
        await callback.answer("⛔ Nu ai acces.", show_alert=True)
        return

    value = callback_data.value
    week_override = None if value == "auto" else value
    await storage.upsert_user_settings(callback.from_user.id, week_override=week_override)

    s = await storage.get_user_settings(callback.from_user.id)
    group = s.get("default_group", "B") if s else "B"

    await callback.message.edit_text(
        _settings_text(group, week_override),
        reply_markup=_settings_keyboard(group, week_override),
        parse_mode="Markdown",
    )
    lbl = "Auto" if week_override is None else week_override.upper()
    await callback.answer(f"Săptămână: {lbl}")
