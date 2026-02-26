"""FSM for marking attendance: Day → WeekType → Group → Session → Status."""
from __future__ import annotations

from datetime import date

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from .. import schedule, storage
from ..config_loader import get as get_config
from ..keyboards import (
    AttendanceCallback,
    DayCallback,
    GroupCallback,
    NavCallback,
    SessionCallback,
    WeekTypeCallback,
    attendance_keyboard,
    days_keyboard,
    group_keyboard,
    sessions_keyboard,
    week_type_keyboard,
)

router = Router()


class MarkStates(StatesGroup):
    choose_day = State()
    choose_week_type = State()
    choose_group = State()
    choose_session = State()
    mark_attendance = State()


def _check(user_id: int) -> bool:
    return user_id in get_config().get("whitelist", [])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

@router.message(F.text == "Marchează prezența")
async def start_mark(message: Message, state: FSMContext) -> None:
    if not _check(message.from_user.id):
        await message.reply("⛔ Nu ai acces.")
        return
    today = schedule.today_bucharest()
    await state.set_state(MarkStates.choose_day)
    await message.reply(
        "📅 *Alege ziua* pentru care marchezi prezența:",
        reply_markup=days_keyboard(today),
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# Cancel (any step)
# ---------------------------------------------------------------------------

@router.callback_query(
    NavCallback.filter(F.action == "cancel"),
    StateFilter(MarkStates),
)
async def cancel_mark(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Operație anulată.")
    await callback.answer()


# ---------------------------------------------------------------------------
# Step 1 → choose day
# ---------------------------------------------------------------------------

@router.callback_query(DayCallback.filter(), StateFilter(MarkStates.choose_day))
async def mark_day(
    callback: CallbackQuery, callback_data: DayCallback, state: FSMContext
) -> None:
    d = date.fromisoformat(callback_data.date_str)
    day_name = schedule.get_day_name(d)
    if day_name is None:
        await callback.answer("Ziua selectată este weekend.", show_alert=True)
        return

    detected_wt = schedule.get_week_type(d) or "impar"
    await state.update_data(
        date_str=callback_data.date_str,
        day_name=day_name,
        detected_week_type=detected_wt,
    )
    await state.set_state(MarkStates.choose_week_type)

    week_label = "IMPARĂ" if detected_wt == "impar" else "PARĂ"
    await callback.message.edit_text(
        f"📅 *{day_name}, {d.strftime('%d.%m.%Y')}*\n\n"
        f"Săptămână auto-detectată: *{week_label}*\n"
        "Confirmă sau schimbă:",
        reply_markup=week_type_keyboard(detected_wt),
        parse_mode="Markdown",
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Back from WeekType → re-show day picker
# ---------------------------------------------------------------------------

@router.callback_query(
    NavCallback.filter(F.action == "back"),
    StateFilter(MarkStates.choose_week_type),
)
async def mark_back_to_day(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(MarkStates.choose_day)
    today = schedule.today_bucharest()
    await callback.message.edit_text(
        "📅 *Alege ziua* pentru care marchezi prezența:",
        reply_markup=days_keyboard(today),
        parse_mode="Markdown",
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Step 2 → choose week type
# ---------------------------------------------------------------------------

@router.callback_query(WeekTypeCallback.filter(), StateFilter(MarkStates.choose_week_type))
async def mark_week_type(
    callback: CallbackQuery, callback_data: WeekTypeCallback, state: FSMContext
) -> None:
    data = await state.get_data()
    wt = callback_data.week_type
    if wt == "auto":
        wt = data["detected_week_type"]
    await state.update_data(week_type=wt)

    settings = await storage.get_user_settings(callback.from_user.id)
    current_group = settings.get("default_group", "B") if settings else "B"

    await state.set_state(MarkStates.choose_group)
    week_label = "IMPARĂ" if wt == "impar" else "PARĂ"
    await callback.message.edit_text(
        f"📅 *{data['day_name']}* | Săpt. *{week_label}*\n\n"
        f"Grupă curentă: *{current_group}*\n"
        "Confirmă sau schimbă grupa:",
        reply_markup=group_keyboard(current_group),
        parse_mode="Markdown",
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Back from Group → re-show week type
# ---------------------------------------------------------------------------

@router.callback_query(
    NavCallback.filter(F.action == "back"),
    StateFilter(MarkStates.choose_group),
)
async def mark_back_to_wt(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(MarkStates.choose_week_type)
    d = date.fromisoformat(data["date_str"])
    week_label = "IMPARĂ" if data.get("detected_week_type") == "impar" else "PARĂ"
    await callback.message.edit_text(
        f"📅 *{data['day_name']}, {d.strftime('%d.%m.%Y')}*\n\n"
        f"Săptămână auto-detectată: *{week_label}*\n"
        "Confirmă sau schimbă:",
        reply_markup=week_type_keyboard(data.get("detected_week_type", "impar")),
        parse_mode="Markdown",
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Step 3 → choose group
# ---------------------------------------------------------------------------

@router.callback_query(GroupCallback.filter(), StateFilter(MarkStates.choose_group))
async def mark_group(
    callback: CallbackQuery, callback_data: GroupCallback, state: FSMContext
) -> None:
    group = callback_data.group
    await state.update_data(group=group)
    data = await state.get_data()

    sessions = await storage.get_sessions_for_day(
        data["day_name"], data["week_type"], group
    )

    if not sessions:
        wt_label = "IMPARĂ" if data["week_type"] == "impar" else "PARĂ"
        await callback.message.edit_text(
            f"📭 Nu sunt ore pentru *{data['day_name']}*, "
            f"Săpt. {wt_label}, Grupa {group}.",
            parse_mode="Markdown",
        )
        await state.clear()
        await callback.answer()
        return

    date_str = data["date_str"]
    for s in sessions:
        att = await storage.get_or_create_attendance(
            callback.from_user.id, s["id"], date_str
        )
        s["status_icon"] = (
            ("✔" if att["status"] == "prezent" else "✖") if att else "—"
        )

    await state.update_data(sessions=sessions)
    await state.set_state(MarkStates.choose_session)
    wt_label = "IMPARĂ" if data["week_type"] == "impar" else "PARĂ"
    await callback.message.edit_text(
        f"📅 *{data['day_name']}* | Săpt. *{wt_label}* | Grupa *{group}*\n\n"
        "Alege ședința:",
        reply_markup=sessions_keyboard(sessions),
        parse_mode="Markdown",
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Back from Session → re-show group
# ---------------------------------------------------------------------------

@router.callback_query(
    NavCallback.filter(F.action == "back"),
    StateFilter(MarkStates.choose_session),
)
async def mark_back_to_group(callback: CallbackQuery, state: FSMContext) -> None:
    settings = await storage.get_user_settings(callback.from_user.id)
    current_group = settings.get("default_group", "B") if settings else "B"
    data = await state.get_data()
    await state.set_state(MarkStates.choose_group)
    wt_label = "IMPARĂ" if data.get("week_type") == "impar" else "PARĂ"
    await callback.message.edit_text(
        f"📅 *{data['day_name']}* | Săpt. *{wt_label}*\n\n"
        f"Grupă curentă: *{current_group}*\n"
        "Confirmă sau schimbă grupa:",
        reply_markup=group_keyboard(current_group),
        parse_mode="Markdown",
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Step 4 → choose session
# ---------------------------------------------------------------------------

@router.callback_query(SessionCallback.filter(), StateFilter(MarkStates.choose_session))
async def mark_session(
    callback: CallbackQuery, callback_data: SessionCallback, state: FSMContext
) -> None:
    session = await storage.get_session_by_id(callback_data.session_id)
    if not session:
        await callback.answer("Ședința nu mai există.", show_alert=True)
        return

    await state.update_data(session_id=callback_data.session_id)
    data = await state.get_data()

    att = await storage.get_or_create_attendance(
        callback.from_user.id, callback_data.session_id, data["date_str"]
    )
    current_status_text = ""
    if att:
        icon = "✔" if att["status"] == "prezent" else "✖"
        current_status_text = f"\nStatus curent: *{icon} {att['status']}*"

    await state.set_state(MarkStates.mark_attendance)
    await callback.message.edit_text(
        f"📚 *{session['subject']}* ({session['session_type']})\n"
        f"🕐 {session['time_start']}‑{session['time_end']}\n"
        f"📍 {session['room']}  👤 _{session['professor']}_\n"
        f"📅 {data['day_name']}, {data['date_str']}"
        f"{current_status_text}\n\n"
        "Marchează prezența:",
        reply_markup=attendance_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Back from Mark → re-show session list
# ---------------------------------------------------------------------------

@router.callback_query(
    NavCallback.filter(F.action == "back"),
    StateFilter(MarkStates.mark_attendance),
)
async def mark_back_to_session(callback: CallbackQuery, state: FSMContext) -> None:
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
    await state.set_state(MarkStates.choose_session)
    wt_label = "IMPARĂ" if data.get("week_type") == "impar" else "PARĂ"
    await callback.message.edit_text(
        f"📅 *{data['day_name']}* | Săpt. *{wt_label}* | Grupa *{data.get('group')}*\n\n"
        "Alege ședința:",
        reply_markup=sessions_keyboard(sessions),
        parse_mode="Markdown",
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Step 5 → mark attendance
# ---------------------------------------------------------------------------

@router.callback_query(AttendanceCallback.filter(), StateFilter(MarkStates.mark_attendance))
async def mark_done(
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
        f"{icon} Ai marcat *{callback_data.status}* pentru:\n"
        f"*{session['subject']}* ({session['session_type']})\n"
        f"📅 {data['date_str']}\n\n"
        "Folosește meniul pentru a continua.",
        parse_mode="Markdown",
    )
    await callback.answer(f"Marcat: {callback_data.status}")
