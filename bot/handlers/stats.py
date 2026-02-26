"""Statistics handler with filter buttons."""
from __future__ import annotations

from typing import Any, Dict, List

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from .. import storage
from ..config_loader import get as get_config
from ..keyboards import StatsFilterCallback, stats_filter_keyboard

router = Router()


def _check(user_id: int) -> bool:
    return user_id in get_config().get("whitelist", [])


def _build_stats_text(stats_raw: List[Dict[str, Any]], filter_type: str = "all") -> str:
    """Aggregate raw stats and format as Markdown text."""
    # Build: {subject: {total, prezente, absente, types: {C/L/P: row}}}
    aggregated: Dict[str, Any] = {}
    for row in stats_raw:
        st = row["session_type"]
        if filter_type != "all" and st != filter_type:
            continue
        subj = row["subject"]
        if subj not in aggregated:
            aggregated[subj] = {"total": 0, "prezente": 0, "absente": 0, "types": {}}
        aggregated[subj]["total"] += row["total"]
        aggregated[subj]["prezente"] += row["prezente"]
        aggregated[subj]["absente"] += row["absente"]
        aggregated[subj]["types"][st] = row

    if not aggregated:
        return "_Nu există date de afișat pentru filtrul selectat._"

    filter_label = {
        "all": "Toate tipurile",
        "C": "Cursuri",
        "L": "Laboratoare",
        "P": "Proiecte",
    }.get(filter_type, filter_type)

    lines = [f"📊 *Statistici prezență* — {filter_label}\n"]
    for subj in sorted(aggregated):
        data = aggregated[subj]
        total = data["total"]
        prez = data["prezente"]
        pct = (prez / total * 100) if total else 0.0
        lines.append(f"*{subj}*: {prez}/{total} ({pct:.1f}%)")
        type_parts = []
        for st in ("C", "L", "P"):
            t = data["types"].get(st)
            if t:
                type_parts.append(f"{st}: {t['prezente']}/{t['total']}")
        if type_parts:
            lines.append("   " + " | ".join(type_parts))
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

@router.message(F.text == "Statistici")
async def stats_handler(message: Message) -> None:
    if not _check(message.from_user.id):
        await message.reply("⛔ Nu ai acces.")
        return

    stats_raw = await storage.get_attendance_stats(message.from_user.id)
    text = _build_stats_text(stats_raw, "all")
    await message.reply(
        text,
        reply_markup=stats_filter_keyboard(),
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# Filter button
# ---------------------------------------------------------------------------

@router.callback_query(StatsFilterCallback.filter())
async def stats_filter(
    callback: CallbackQuery, callback_data: StatsFilterCallback
) -> None:
    if not _check(callback.from_user.id):
        await callback.answer("⛔ Nu ai acces.", show_alert=True)
        return

    stats_raw = await storage.get_attendance_stats(callback.from_user.id)
    text = _build_stats_text(stats_raw, callback_data.filter_type)
    await callback.message.edit_text(
        text,
        reply_markup=stats_filter_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()
