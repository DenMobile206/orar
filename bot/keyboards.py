"""Keyboard factories and shared CallbackData classes."""
from __future__ import annotations

from datetime import date, timedelta
from typing import List, Dict, Any

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


# ---------------------------------------------------------------------------
# CallbackData classes
# ---------------------------------------------------------------------------

class NavCallback(CallbackData, prefix="nav"):
    action: str  # cancel | back


class DayCallback(CallbackData, prefix="day"):
    date_str: str


class WeekTypeCallback(CallbackData, prefix="wt"):
    week_type: str  # impar | par | auto


class GroupCallback(CallbackData, prefix="grp"):
    group: str  # A | B


class SessionCallback(CallbackData, prefix="sess"):
    session_id: int


class AttendanceCallback(CallbackData, prefix="att"):
    status: str  # prezent | absent


class StatsFilterCallback(CallbackData, prefix="stats"):
    filter_type: str  # all | C | L | P


class AdminCallback(CallbackData, prefix="admin"):
    action: str  # view | add | edit | delete | backup


class AdminSessionCallback(CallbackData, prefix="admin_sess"):
    session_id: int
    action: str  # edit | delete


class AdminFieldCallback(CallbackData, prefix="admin_field"):
    field: str


class AdminDayCallback(CallbackData, prefix="admin_day"):
    day: str


class AdminWTCallback(CallbackData, prefix="admin_wt"):
    week_type: str


class AdminGroupCallback(CallbackData, prefix="admin_grp"):
    group: str


class AdminTimeCallback(CallbackData, prefix="admin_time"):
    slot: str  # "08:00-09:50" etc.


class AdminTypeCallback(CallbackData, prefix="admin_type"):
    session_type: str  # C | L | P


class SettingsCallback(CallbackData, prefix="settings"):
    action: str
    value: str = ""


# ---------------------------------------------------------------------------
# Reply keyboard
# ---------------------------------------------------------------------------

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.button(text="Astăzi")
    b.button(text="Alege zi")
    b.button(text="Marchează prezența")
    b.button(text="Editează")
    b.button(text="Statistici")
    b.button(text="Export Excel")
    b.button(text="Setări")
    b.button(text="Admin: Orare")
    b.adjust(2)
    return b.as_markup(resize_keyboard=True)


# ---------------------------------------------------------------------------
# Inline keyboards
# ---------------------------------------------------------------------------

def days_keyboard(current_date: date, n_days: int = 7) -> InlineKeyboardMarkup:
    """Last *n_days* days (oldest first) + today, skipping weekends."""
    from .schedule import get_day_name, is_vacation  # local to avoid circular

    b = InlineKeyboardBuilder()
    for i in range(n_days - 1, -1, -1):
        d = current_date - timedelta(days=i)
        day_name = get_day_name(d)
        if day_name is None:
            continue
        label = f"{day_name}, {d.strftime('%d.%m')}"
        if i == 0:
            label += " (azi)"
        if is_vacation(d):
            label += " 🏖"
        b.button(text=label, callback_data=DayCallback(date_str=d.isoformat()))
    b.button(text="✖ Anulează", callback_data=NavCallback(action="cancel"))
    b.adjust(1)
    return b.as_markup()


def week_type_keyboard(current_type: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    options = [("auto", "🔄 Auto"), ("impar", "Săpt. IMPARĂ"), ("par", "Săpt. PARĂ")]
    for wt, label in options:
        prefix = "✔ " if current_type == wt else ""
        b.button(text=f"{prefix}{label}", callback_data=WeekTypeCallback(week_type=wt))
    b.button(text="↩ Înapoi", callback_data=NavCallback(action="back"))
    b.adjust(1)
    return b.as_markup()


def group_keyboard(current_group: str = "") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for g in ("A", "B"):
        prefix = "✔ " if current_group == g else ""
        b.button(text=f"{prefix}Grupa {g}", callback_data=GroupCallback(group=g))
    b.button(text="↩ Înapoi", callback_data=NavCallback(action="back"))
    b.adjust(2)
    return b.as_markup()


def sessions_keyboard(sessions: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for s in sessions:
        icon = s.get("status_icon", "—")
        text = f"{icon} {s['time_start']} {s['subject']}({s['session_type']})"
        b.button(text=text, callback_data=SessionCallback(session_id=s["id"]))
    b.button(text="↩ Înapoi", callback_data=NavCallback(action="back"))
    b.adjust(1)
    return b.as_markup()


def attendance_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✔ Prezent", callback_data=AttendanceCallback(status="prezent"))
    b.button(text="✖ Absent",  callback_data=AttendanceCallback(status="absent"))
    b.button(text="↩ Înapoi",  callback_data=NavCallback(action="back"))
    b.adjust(2)
    return b.as_markup()


def stats_filter_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for ft, label in [("all", "📊 Toate"), ("C", "📖 Curs"), ("L", "🔬 Laborator"), ("P", "📐 Proiect")]:
        b.button(text=label, callback_data=StatsFilterCallback(filter_type=ft))
    b.adjust(2)
    return b.as_markup()


def admin_schedule_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📋 Vezi orar",          callback_data=AdminCallback(action="view"))
    b.button(text="➕ Adaugă ședință",     callback_data=AdminCallback(action="add"))
    b.button(text="✏️ Editează ședință",   callback_data=AdminCallback(action="edit"))
    b.button(text="🗑 Șterge ședință",     callback_data=AdminCallback(action="delete"))
    b.button(text="💾 Backup/Export orar", callback_data=AdminCallback(action="backup"))
    b.button(text="✖ Închide",             callback_data=NavCallback(action="cancel"))
    b.adjust(1)
    return b.as_markup()


def admin_days_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for day in ("Luni", "Marți", "Miercuri", "Joi", "Vineri"):
        b.button(text=day, callback_data=AdminDayCallback(day=day))
    b.button(text="↩ Înapoi", callback_data=NavCallback(action="back"))
    b.adjust(2)
    return b.as_markup()


def admin_week_type_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for wt, label in [("impar", "Săpt. IMPARĂ"), ("par", "Săpt. PARĂ"), ("both", "Ambele")]:
        b.button(text=label, callback_data=AdminWTCallback(week_type=wt))
    b.button(text="↩ Înapoi", callback_data=NavCallback(action="back"))
    b.adjust(2)
    return b.as_markup()


def admin_group_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for g, label in [("A", "Grupa A"), ("B", "Grupa B"), ("both", "Ambele grupe")]:
        b.button(text=label, callback_data=AdminGroupCallback(group=g))
    b.button(text="↩ Înapoi", callback_data=NavCallback(action="back"))
    b.adjust(2)
    return b.as_markup()


def admin_time_keyboard() -> InlineKeyboardMarkup:
    slots = [
        "08:00-09:50", "10:00-11:50", "12:00-13:50",
        "14:00-15:50", "16:00-17:50", "18:00-19:50",
    ]
    b = InlineKeyboardBuilder()
    for slot in slots:
        b.button(text=slot, callback_data=AdminTimeCallback(slot=slot))
    b.button(text="↩ Înapoi", callback_data=NavCallback(action="back"))
    b.adjust(2)
    return b.as_markup()


def admin_session_type_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for t, label in [("C", "Curs (C)"), ("L", "Laborator (L)"), ("P", "Proiect (P)")]:
        b.button(text=label, callback_data=AdminTypeCallback(session_type=t))
    b.button(text="↩ Înapoi", callback_data=NavCallback(action="back"))
    b.adjust(2)
    return b.as_markup()


def admin_sessions_list_keyboard(
    sessions: List[Dict[str, Any]], action: str
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for s in sessions:
        label = f"{s['day'][:2]} {s['week_type'][:3]} {s['group_code']} | {s['time_start']} {s['subject']}({s['session_type']})"
        b.button(
            text=label,
            callback_data=AdminSessionCallback(session_id=s["id"], action=action),
        )
    b.button(text="↩ Înapoi", callback_data=NavCallback(action="back"))
    b.adjust(1)
    return b.as_markup()


def admin_edit_field_keyboard() -> InlineKeyboardMarkup:
    fields = [
        ("day", "Zi"), ("week_type", "Tip săpt."), ("group_code", "Grupă"),
        ("subject", "Disciplină"), ("session_type", "Tip ședință"),
        ("room", "Sală"), ("time_start", "Ora start"), ("time_end", "Ora end"),
        ("professor", "Profesor"),
    ]
    b = InlineKeyboardBuilder()
    for field, label in fields:
        b.button(text=label, callback_data=AdminFieldCallback(field=field))
    b.button(text="↩ Înapoi", callback_data=NavCallback(action="back"))
    b.adjust(2)
    return b.as_markup()
