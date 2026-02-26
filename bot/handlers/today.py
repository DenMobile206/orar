"""Handlers for 'Astăzi' and 'Alege zi' buttons."""
from __future__ import annotations

from datetime import date

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from .. import schedule, storage
from ..config_loader import get as get_config
from ..keyboards import DayCallback, NavCallback, days_keyboard

router = Router()


class ViewDayStates(StatesGroup):
    choose_day = State()


def _check(user_id: int) -> bool:
    return user_id in get_config().get("whitelist", [])


# ---------------------------------------------------------------------------
# "Astăzi"
# ---------------------------------------------------------------------------

@router.message(F.text == "Astăzi")
async def today_handler(message: Message) -> None:
    if not _check(message.from_user.id):
        await message.reply("⛔ Nu ai acces.")
        return
    await _show_day(message, schedule.today_bucharest(), send_new=True)


# ---------------------------------------------------------------------------
# "Alege zi"
# ---------------------------------------------------------------------------

@router.message(F.text == "Alege zi")
async def choose_day_start(message: Message, state: FSMContext) -> None:
    if not _check(message.from_user.id):
        await message.reply("⛔ Nu ai acces.")
        return
    await state.set_state(ViewDayStates.choose_day)
    await message.reply(
        "📅 Alege ziua pe care vrei s-o vizualizezi:",
        reply_markup=days_keyboard(schedule.today_bucharest()),
    )


@router.callback_query(DayCallback.filter(), StateFilter(ViewDayStates.choose_day))
async def choose_day_callback(
    callback: CallbackQuery, callback_data: DayCallback, state: FSMContext
) -> None:
    await state.clear()
    d = date.fromisoformat(callback_data.date_str)
    await _show_day(callback.message, d, send_new=False)
    await callback.answer()


@router.callback_query(NavCallback.filter(F.action == "cancel"), StateFilter(ViewDayStates.choose_day))
async def choose_day_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Operație anulată.")
    await callback.answer()


# ---------------------------------------------------------------------------
# Shared display helper
# ---------------------------------------------------------------------------

async def _show_day(target: Message, d: date, *, send_new: bool) -> None:
    user_id = target.chat.id

    day_name = schedule.get_day_name(d)
    if day_name is None:
        text = "🏠 Weekend! Nu sunt ore programate."
        if send_new:
            await target.reply(text)
        else:
            await target.edit_text(text)
        return

    if schedule.is_vacation(d):
        text = "🏖 Vacanță! Nu sunt ore programate."
        if send_new:
            await target.reply(text)
        else:
            await target.edit_text(text)
        return

    settings = await storage.get_user_settings(user_id)
    if not settings:
        config = get_config()
        settings = {"default_group": config.get("default_group", "B"), "week_override": None}

    week_type = schedule.get_week_type(d, override=settings.get("week_override"))
    group = settings.get("default_group", "B")

    if week_type is None:
        text = "📭 Această zi nu face parte din perioadele de curs."
        if send_new:
            await target.reply(text)
        else:
            await target.edit_text(text)
        return

    sessions = await storage.get_sessions_for_day(day_name, week_type, group)
    week_label = "IMPARĂ" if week_type == "impar" else "PARĂ"

    lines = [
        f"📅 *{day_name}, {d.strftime('%d.%m.%Y')}*",
        f"Săptămâna {week_label} | Grupa {group}",
        "",
    ]

    if not sessions:
        lines.append("_Nu sunt ore programate pentru această zi/grupă._")
    else:
        date_str = d.isoformat()
        for s in sessions:
            att = await storage.get_or_create_attendance(user_id, s["id"], date_str)
            if att:
                icon = "✔" if att["status"] == "prezent" else "✖"
            else:
                icon = "—"
            lines.append(
                f"{icon} `{s['time_start']}`‑`{s['time_end']}` "
                f"*{s['subject']}* ({s['session_type']})"
            )
            lines.append(f"    📍 {s['room']}  👤 _{s['professor']}_")
            lines.append("")

    text = "\n".join(lines)
    if send_new:
        await target.reply(text, parse_mode="Markdown")
    else:
        await target.edit_text(text, parse_mode="Markdown")
