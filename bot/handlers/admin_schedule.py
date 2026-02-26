"""Admin schedule management: view, add, edit, delete, backup."""
from __future__ import annotations

import json

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .. import storage
from ..config_loader import get as get_config
from ..keyboards import (
    AdminCallback,
    AdminDayCallback,
    AdminFieldCallback,
    AdminGroupCallback,
    AdminSessionCallback,
    AdminTimeCallback,
    AdminTypeCallback,
    AdminWTCallback,
    NavCallback,
    admin_days_keyboard,
    admin_edit_field_keyboard,
    admin_group_keyboard,
    admin_schedule_keyboard,
    admin_session_type_keyboard,
    admin_sessions_list_keyboard,
    admin_time_keyboard,
    admin_week_type_keyboard,
)

router = Router()

DAYS_ORDER = ["Luni", "Marți", "Miercuri", "Joi", "Vineri"]


def _check(user_id: int) -> bool:
    return user_id in get_config().get("whitelist", [])


# ===========================================================================
# FSM
# ===========================================================================

class AdminStates(StatesGroup):
    # View flow
    view_day = State()
    view_wt = State()
    view_group = State()

    # Add flow
    add_day = State()
    add_wt = State()
    add_time = State()
    add_subject = State()
    add_session_type = State()
    add_room = State()
    add_professor = State()
    add_group = State()

    # Edit flow
    edit_select = State()
    edit_field = State()
    edit_value = State()

    # Delete flow
    delete_select = State()
    delete_confirm = State()


# ===========================================================================
# Helpers
# ===========================================================================

def _session_label(s: dict) -> str:
    return (
        f"{s['day']} | {s['week_type']} | Gr.{s['group_code']} | "
        f"{s['time_start']} {s['subject']}({s['session_type']}) {s['room']}"
    )


# ===========================================================================
# Entry point
# ===========================================================================

@router.message(F.text == "Admin: Orare")
async def admin_menu(message: Message, state: FSMContext) -> None:
    if not _check(message.from_user.id):
        await message.reply("⛔ Nu ai acces.")
        return
    await state.clear()
    await message.reply(
        "🛠 *Admin – Gestionare orare*\n\nAlege o acțiune:",
        reply_markup=admin_schedule_keyboard(),
        parse_mode="Markdown",
    )


# Cancel from any admin state
@router.callback_query(NavCallback.filter(F.action == "cancel"), StateFilter(AdminStates))
async def admin_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Operație anulată.")
    await callback.answer()


# Back to admin menu
@router.callback_query(NavCallback.filter(F.action == "back"), StateFilter(AdminStates))
async def admin_back_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "🛠 *Admin – Gestionare orare*\n\nAlege o acțiune:",
        reply_markup=admin_schedule_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


# ===========================================================================
# VIEW flow
# ===========================================================================

@router.callback_query(AdminCallback.filter(F.action == "view"))
async def admin_view_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _check(callback.from_user.id):
        await callback.answer("⛔ Nu ai acces.", show_alert=True)
        return
    await state.set_state(AdminStates.view_day)
    await callback.message.edit_text(
        "📋 *Vezi orar* – alege ziua:",
        reply_markup=admin_days_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(AdminDayCallback.filter(), StateFilter(AdminStates.view_day))
async def admin_view_day(
    callback: CallbackQuery, callback_data: AdminDayCallback, state: FSMContext
) -> None:
    await state.update_data(day=callback_data.day)
    await state.set_state(AdminStates.view_wt)
    await callback.message.edit_text(
        f"📋 Ziua: *{callback_data.day}* – alege tipul de săptămână:",
        reply_markup=admin_week_type_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(AdminWTCallback.filter(), StateFilter(AdminStates.view_wt))
async def admin_view_wt(
    callback: CallbackQuery, callback_data: AdminWTCallback, state: FSMContext
) -> None:
    await state.update_data(week_type=callback_data.week_type)
    await state.set_state(AdminStates.view_group)
    await callback.message.edit_text(
        "📋 Alege grupa:",
        reply_markup=admin_group_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(AdminGroupCallback.filter(), StateFilter(AdminStates.view_group))
async def admin_view_group(
    callback: CallbackQuery, callback_data: AdminGroupCallback, state: FSMContext
) -> None:
    data = await state.get_data()
    day = data["day"]
    wt = data["week_type"]
    group = callback_data.group

    if wt == "both":
        sessions_i = await storage.get_sessions_for_day(day, "impar", group)
        sessions_p = await storage.get_sessions_for_day(day, "par", group)
        # deduplicate by id
        seen = set()
        sessions = []
        for s in sessions_i + sessions_p:
            if s["id"] not in seen:
                seen.add(s["id"])
                sessions.append(s)
    else:
        sessions = await storage.get_sessions_for_day(day, wt, group)

    await state.clear()
    if not sessions:
        await callback.message.edit_text(
            f"📭 Nu sunt ședințe pentru {day} / {wt} / Gr.{group}.",
            reply_markup=admin_schedule_keyboard(),
        )
        await callback.answer()
        return

    lines = [f"📋 *Orar: {day} | {wt} | Gr.{group}*\n"]
    for s in sessions:
        lines.append(
            f"• [{s['id']}] `{s['time_start']}`‑`{s['time_end']}` "
            f"*{s['subject']}*({s['session_type']}) 📍{s['room']} 👤_{s['professor']}_"
        )
    lines.append("\n_Folosește meniul pentru alte acțiuni._")
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=admin_schedule_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


# ===========================================================================
# ADD flow
# ===========================================================================

@router.callback_query(AdminCallback.filter(F.action == "add"))
async def admin_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _check(callback.from_user.id):
        await callback.answer("⛔ Nu ai acces.", show_alert=True)
        return
    await state.set_state(AdminStates.add_day)
    await callback.message.edit_text(
        "➕ *Adaugă ședință* – Pas 1: alege ziua",
        reply_markup=admin_days_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(AdminDayCallback.filter(), StateFilter(AdminStates.add_day))
async def admin_add_day(
    callback: CallbackQuery, callback_data: AdminDayCallback, state: FSMContext
) -> None:
    await state.update_data(day=callback_data.day)
    await state.set_state(AdminStates.add_wt)
    await callback.message.edit_text(
        f"➕ Ziua: *{callback_data.day}* – Pas 2: tipul de săptămână",
        reply_markup=admin_week_type_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(AdminWTCallback.filter(), StateFilter(AdminStates.add_wt))
async def admin_add_wt(
    callback: CallbackQuery, callback_data: AdminWTCallback, state: FSMContext
) -> None:
    await state.update_data(week_type=callback_data.week_type)
    await state.set_state(AdminStates.add_time)
    await callback.message.edit_text(
        "➕ Pas 3: alege intervalul orar",
        reply_markup=admin_time_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(AdminTimeCallback.filter(), StateFilter(AdminStates.add_time))
async def admin_add_time(
    callback: CallbackQuery, callback_data: AdminTimeCallback, state: FSMContext
) -> None:
    parts = callback_data.slot.split("-")
    await state.update_data(time_start=parts[0], time_end=parts[1])
    await state.set_state(AdminStates.add_subject)
    await callback.message.edit_text(
        "➕ Pas 4: scrie *numele disciplinei* (ex: SN, PIUG, O …):",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(StateFilter(AdminStates.add_subject))
async def admin_add_subject(message: Message, state: FSMContext) -> None:
    await state.update_data(subject=message.text.strip())
    await state.set_state(AdminStates.add_session_type)
    await message.reply(
        "➕ Pas 5: tipul ședinței (C / L / P):",
        reply_markup=admin_session_type_keyboard(),
    )


@router.callback_query(AdminTypeCallback.filter(), StateFilter(AdminStates.add_session_type))
async def admin_add_session_type(
    callback: CallbackQuery, callback_data: AdminTypeCallback, state: FSMContext
) -> None:
    await state.update_data(session_type=callback_data.session_type)
    await state.set_state(AdminStates.add_room)
    await callback.message.edit_text("➕ Pas 6: scrie *sala* (ex: Y401, AN101 …):", parse_mode="Markdown")
    await callback.answer()


@router.message(StateFilter(AdminStates.add_room))
async def admin_add_room(message: Message, state: FSMContext) -> None:
    await state.update_data(room=message.text.strip())
    await state.set_state(AdminStates.add_professor)
    await message.reply("➕ Pas 7: scrie *numele profesorului*:", parse_mode="Markdown")


@router.message(StateFilter(AdminStates.add_professor))
async def admin_add_professor(message: Message, state: FSMContext) -> None:
    await state.update_data(professor=message.text.strip())
    await state.set_state(AdminStates.add_group)
    await message.reply(
        "➕ Pas 8: alege *grupa*:",
        reply_markup=admin_group_keyboard(),
        parse_mode="Markdown",
    )


@router.callback_query(AdminGroupCallback.filter(), StateFilter(AdminStates.add_group))
async def admin_add_group(
    callback: CallbackQuery, callback_data: AdminGroupCallback, state: FSMContext
) -> None:
    await state.update_data(group=callback_data.group)
    data = await state.get_data()
    await state.clear()

    new_id = await storage.add_session(
        day=data["day"],
        week_type=data["week_type"],
        group_code=data["group"],
        subject=data["subject"],
        session_type=data["session_type"],
        room=data["room"],
        time_start=data["time_start"],
        time_end=data["time_end"],
        professor=data["professor"],
    )
    await callback.message.edit_text(
        f"✅ Ședință adăugată (ID={new_id}):\n"
        f"*{data['subject']}* ({data['session_type']}) {data['day']} | "
        f"{data['week_type']} | Gr.{data['group']} | "
        f"{data['time_start']}‑{data['time_end']} | {data['room']} | {data['professor']}",
        reply_markup=admin_schedule_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer("Ședință adăugată!")


# ===========================================================================
# EDIT flow
# ===========================================================================

@router.callback_query(AdminCallback.filter(F.action == "edit"))
async def admin_edit_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _check(callback.from_user.id):
        await callback.answer("⛔ Nu ai acces.", show_alert=True)
        return
    sessions = await storage.get_all_sessions()
    if not sessions:
        await callback.message.edit_text(
            "📭 Nu există ședințe active.",
            reply_markup=admin_schedule_keyboard(),
        )
        await callback.answer()
        return
    await state.set_state(AdminStates.edit_select)
    await callback.message.edit_text(
        "✏️ *Editează ședință* – alege ședința:",
        reply_markup=admin_sessions_list_keyboard(sessions, "edit"),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(AdminSessionCallback.filter(F.action == "edit"), StateFilter(AdminStates.edit_select))
async def admin_edit_select(
    callback: CallbackQuery, callback_data: AdminSessionCallback, state: FSMContext
) -> None:
    s = await storage.get_session_by_id(callback_data.session_id)
    if not s:
        await callback.answer("Ședința nu mai există.", show_alert=True)
        return
    await state.update_data(session_id=callback_data.session_id)
    await state.set_state(AdminStates.edit_field)
    await callback.message.edit_text(
        f"✏️ *{_session_label(s)}*\n\nCe câmp vrei să modifici?",
        reply_markup=admin_edit_field_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(AdminFieldCallback.filter(), StateFilter(AdminStates.edit_field))
async def admin_edit_field(
    callback: CallbackQuery, callback_data: AdminFieldCallback, state: FSMContext
) -> None:
    await state.update_data(edit_field=callback_data.field)
    await state.set_state(AdminStates.edit_value)
    await callback.message.edit_text(
        f"✏️ Câmp: *{callback_data.field}*\n\nScrie noua valoare:",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(StateFilter(AdminStates.edit_value))
async def admin_edit_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    field = data["edit_field"]
    value = message.text.strip()
    await storage.update_session(data["session_id"], **{field: value})
    await state.clear()
    s = await storage.get_session_by_id(data["session_id"])
    await message.reply(
        f"✅ Câmpul *{field}* actualizat la `{value}`.\n"
        + (f"Ședință: {_session_label(s)}" if s else ""),
        reply_markup=admin_schedule_keyboard(),
        parse_mode="Markdown",
    )


# ===========================================================================
# DELETE flow
# ===========================================================================

@router.callback_query(AdminCallback.filter(F.action == "delete"))
async def admin_delete_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _check(callback.from_user.id):
        await callback.answer("⛔ Nu ai acces.", show_alert=True)
        return
    sessions = await storage.get_all_sessions()
    if not sessions:
        await callback.message.edit_text(
            "📭 Nu există ședințe active.",
            reply_markup=admin_schedule_keyboard(),
        )
        await callback.answer()
        return
    await state.set_state(AdminStates.delete_select)
    await callback.message.edit_text(
        "🗑 *Șterge ședință* – alege ședința:",
        reply_markup=admin_sessions_list_keyboard(sessions, "delete"),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(
    AdminSessionCallback.filter(F.action == "delete"),
    StateFilter(AdminStates.delete_select),
)
async def admin_delete_select(
    callback: CallbackQuery, callback_data: AdminSessionCallback, state: FSMContext
) -> None:
    s = await storage.get_session_by_id(callback_data.session_id)
    if not s:
        await callback.answer("Ședința nu mai există.", show_alert=True)
        return
    await state.update_data(session_id=callback_data.session_id)
    await state.set_state(AdminStates.delete_confirm)

    b = InlineKeyboardBuilder()
    b.button(text="✅ Da, șterge", callback_data=AdminCallback(action="delete_confirm"))
    b.button(text="↩ Înapoi",      callback_data=NavCallback(action="back"))
    b.adjust(2)

    await callback.message.edit_text(
        f"🗑 Confirmi ștergerea?\n\n*{_session_label(s)}*",
        reply_markup=b.as_markup(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(
    AdminCallback.filter(F.action == "delete_confirm"),
    StateFilter(AdminStates.delete_confirm),
)
async def admin_delete_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await storage.delete_session(data["session_id"])
    await state.clear()
    await callback.message.edit_text(
        f"✅ Ședința (ID={data['session_id']}) a fost dezactivată.",
        reply_markup=admin_schedule_keyboard(),
    )
    await callback.answer("Șters!")


# ===========================================================================
# BACKUP / EXPORT flow
# ===========================================================================

@router.callback_query(AdminCallback.filter(F.action == "backup"))
async def admin_backup(callback: CallbackQuery) -> None:
    if not _check(callback.from_user.id):
        await callback.answer("⛔ Nu ai acces.", show_alert=True)
        return

    sessions = await storage.get_all_sessions()
    json_bytes = json.dumps(sessions, ensure_ascii=False, indent=2).encode("utf-8")
    file = BufferedInputFile(json_bytes, filename="orar_backup.json")
    await callback.message.reply_document(
        document=file,
        caption="💾 Backup orar complet (JSON)",
    )
    await callback.answer("Export trimis!")
