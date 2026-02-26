"""FSM for editing existing attendance records: Day → Session → Status."""
from __future__ import annotations

from datetime import date

from typing import Any, Dict, List, Optional

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from aiogram.utils.keyboard import InlineKeyboardBuilder

from .. import schedule, storage
from ..config_loader import get as get_config
from ..keyboards import (
    AttendanceCallback,
    DayCallback,
    NavCallback,
    SessionCallback,
    attendance_keyboard,
    sessions_keyboard,
)

router = Router()


class EditStates(StatesGroup):
    choose_day = State()
    choose_session = State()
    mark_attendance = State()


def _check(user_id: int) -> bool:
    return user_id in get_config().get("whitelist", [])


def _attendance_dates_keyboard(dates: List[str]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for d_str in dates:
        d = date.fromisoformat(d_str)
        day_name = schedule.get_day_name(d) or d.strftime("%a")
        b.button(
            text=f"{day_name}, {d.strftime('%d.%m.%Y')}",
            callback_data=DayCallback(date_str=d_str),
        )
    b.button(text="✖ Anulează", callback_data=NavCallback(action="cancel"))
    b.adjust(1)
    return b.as_markup()


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

@router.message(F.text == "Editează")
async def start_edit(message: Message, state: FSMContext) -> None:
    if not _check(message.from_user.id):
        await message.reply("⛔ Nu ai acces.")
        return

    dates = await storage.get_attendance_dates(message.from_user.id)
    if not dates:
        await message.reply("📭 Nu ai nicio prezență înregistrată până acum.")
        return

    await state.set_state(EditStates.choose_day)
    await message.reply(
        "✏️ *Editează prezența* – alege ziua:",
        reply_markup=_attendance_dates_keyboard(dates),
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# Cancel (any step)
# ---------------------------------------------------------------------------

@router.callback_query(NavCallback.filter(F.action == "cancel"), StateFilter(EditStates))
async def cancel_edit(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Operație anulată.")
    await callback.answer()


# ---------------------------------------------------------------------------
# Step 1 → choose day
# ---------------------------------------------------------------------------

@router.callback_query(DayCallback.filter(), StateFilter(EditStates.choose_day))
async def edit_day(
    callback: CallbackQuery, callback_data: DayCallback, state: FSMContext
) -> None:
    date_str = callback_data.date_str
    user_id = callback.from_user.id

    settings = await storage.get_user_settings(user_id)
    group = settings.get("default_group", "B") if settings else "B"

    d = date.fromisoformat(date_str)
    day_name = schedule.get_day_name(d) or d.strftime("%A")
    week_type = schedule.get_week_type(d) or "impar"

    sessions = await storage.get_sessions_for_day(day_name, week_type, group)
    # Only show sessions that have recorded attendance on this date
    attended = []
    for s in sessions:
        att = await storage.get_or_create_attendance(user_id, s["id"], date_str)
        if att:
            s["status_icon"] = "✔" if att["status"] == "prezent" else "✖"
            attended.append(s)

    if not attended:
        await callback.message.edit_text(
            f"📭 Nu există prezențe înregistrate pentru *{day_name}, {d.strftime('%d.%m.%Y')}*.",
            parse_mode="Markdown",
        )
        await state.clear()
        await callback.answer()
        return

    await state.update_data(
        date_str=date_str,
        day_name=day_name,
        week_type=week_type,
        group=group,
        sessions=attended,
    )
    await state.set_state(EditStates.choose_session)
    wt_label = "IMPARĂ" if week_type == "impar" else "PARĂ"
    await callback.message.edit_text(
        f"✏️ *{day_name}, {d.strftime('%d.%m.%Y')}* | Săpt. {wt_label} | Grupa {group}\n\n"
        "Alege ședința de editat:",
        reply_markup=sessions_keyboard(attended),
        parse_mode="Markdown",
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Back from Session → re-show day list
# ---------------------------------------------------------------------------

@router.callback_query(
    NavCallback.filter(F.action == "back"),
    StateFilter(EditStates.choose_session),
)
async def edit_back_to_day(callback: CallbackQuery, state: FSMContext) -> None:
    dates = await storage.get_attendance_dates(callback.from_user.id)
    await state.set_state(EditStates.choose_day)
    await callback.message.edit_text(
        "✏️ *Editează prezența* – alege ziua:",
        reply_markup=_attendance_dates_keyboard(dates),
        parse_mode="Markdown",
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Step 2 → choose session
# ---------------------------------------------------------------------------

@router.callback_query(SessionCallback.filter(), StateFilter(EditStates.choose_session))
async def edit_session(
    callback: CallbackQuery, callback_data: SessionCallback, state: FSMContext
) -> None:
    session = await storage.get_session_by_id(callback_data.session_id)
    if not session:
        await callback.answer("Ședința nu mai există.", show_alert=True)
        return

    data = await state.get_data()
    att = await storage.get_or_create_attendance(
        callback.from_user.id, callback_data.session_id, data["date_str"]
    )
    current = att["status"] if att else "—"
    icon = "✔" if current == "prezent" else ("✖" if current == "absent" else "—")

    await state.update_data(session_id=callback_data.session_id)
    await state.set_state(EditStates.mark_attendance)
    await callback.message.edit_text(
        f"📚 *{session['subject']}* ({session['session_type']})\n"
        f"🕐 {session['time_start']}‑{session['time_end']}\n"
        f"📍 {session['room']}  👤 _{session['professor']}_\n"
        f"📅 {data['day_name']}, {data['date_str']}\n\n"
        f"Status actual: *{icon} {current}*\n\n"
        "Schimbă în:",
        reply_markup=attendance_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Back from Mark → re-show session list
# ---------------------------------------------------------------------------

@router.callback_query(
    NavCallback.filter(F.action == "back"),
    StateFilter(EditStates.mark_attendance),
)
async def edit_back_to_session(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    sessions = data.get("sessions", [])
    date_str = data.get("date_str", "")
    for s in sessions:
        att = await storage.get_or_create_attendance(
            callback.from_user.id, s["id"], date_str
        )
        s["status_icon"] = (
            ("✔" if att["status"] == "prezent" else "✖") if att else "—"
        )
    await state.set_state(EditStates.choose_session)
    wt_label = "IMPARĂ" if data.get("week_type") == "impar" else "PARĂ"
    await callback.message.edit_text(
        f"✏️ *{data['day_name']}* | Săpt. {wt_label} | Grupa {data.get('group')}\n\n"
        "Alege ședința de editat:",
        reply_markup=sessions_keyboard(sessions),
        parse_mode="Markdown",
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Step 3 → save new status
# ---------------------------------------------------------------------------

@router.callback_query(AttendanceCallback.filter(), StateFilter(EditStates.mark_attendance))
async def edit_done(
    callback: CallbackQuery, callback_data: AttendanceCallback, state: FSMContext
) -> None:
    data = await state.get_data()
    await storage.upsert_attendance(
        callback.from_user.id,
        data["session_id"],
        data["date_str"],
        callback_data.status,
    )
    session = await storage.get_session_by_id(data["session_id"])
    icon = "✔" if callback_data.status == "prezent" else "✖"
    await state.clear()
    await callback.message.edit_text(
        f"{icon} Status actualizat la *{callback_data.status}* pentru:\n"
        f"*{session['subject']}* ({session['session_type']})\n"
        f"📅 {data['date_str']}",
        parse_mode="Markdown",
    )
    await callback.answer("Actualizat!")
