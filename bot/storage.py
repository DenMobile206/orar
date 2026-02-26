"""Async SQLite storage layer via aiosqlite."""
import aiosqlite
from typing import Optional, List, Dict, Any
from datetime import datetime
import pytz

_db_path = "attendance.db"
_TZ = pytz.timezone("Europe/Bucharest")


def set_db_path(path: str) -> None:
    global _db_path
    _db_path = path


def _now_iso() -> str:
    return datetime.now(_TZ).isoformat()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

async def init_db(db_path: str) -> None:
    set_db_path(db_path)
    async with aiosqlite.connect(_db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS schedule_sessions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                day          TEXT NOT NULL,
                week_type    TEXT NOT NULL DEFAULT 'both',
                group_code   TEXT NOT NULL DEFAULT 'both',
                subject      TEXT NOT NULL,
                session_type TEXT NOT NULL,
                room         TEXT NOT NULL,
                time_start   TEXT NOT NULL,
                time_end     TEXT NOT NULL,
                professor    TEXT NOT NULL,
                is_active    INTEGER NOT NULL DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                session_id  INTEGER NOT NULL,
                date        TEXT NOT NULL,
                status      TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                UNIQUE(user_id, session_id, date)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id       INTEGER PRIMARY KEY,
                default_group TEXT NOT NULL DEFAULT 'B',
                week_override TEXT,
                updated_at    TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS schedule_imported (
                id       INTEGER PRIMARY KEY,
                imported INTEGER NOT NULL DEFAULT 0
            )
        """)
        await db.commit()


# ---------------------------------------------------------------------------
# Schedule import
# ---------------------------------------------------------------------------

async def is_schedule_imported() -> bool:
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT imported FROM schedule_imported WHERE id = 1")
        row = await cur.fetchone()
        return bool(row and row["imported"])


async def import_schedule_from_config(config: Dict[str, Any]) -> None:
    """Populate schedule_sessions from config.yaml (runs once)."""
    if await is_schedule_imported():
        return

    schedule = config.get("schedule", {})
    async with aiosqlite.connect(_db_path) as db:
        for day, week_types in schedule.items():
            for week_type, groups in week_types.items():
                for group_code, sessions in groups.items():
                    for s in sessions:
                        await db.execute(
                            """
                            INSERT INTO schedule_sessions
                                (day, week_type, group_code, subject, session_type,
                                 room, time_start, time_end, professor, is_active)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                            """,
                            (
                                day,
                                week_type,
                                group_code,
                                s["subject"],
                                s["session_type"],
                                s["room"],
                                s["time_start"],
                                s["time_end"],
                                s["professor"],
                            ),
                        )
        await db.execute(
            "INSERT OR REPLACE INTO schedule_imported (id, imported) VALUES (1, 1)"
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

async def get_sessions_for_day(
    day: str, week_type: str, group: str
) -> List[Dict[str, Any]]:
    """Return sessions matching day + (week_type or 'both') + (group or 'both')."""
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT * FROM schedule_sessions
            WHERE day = ?
              AND week_type IN ('both', ?)
              AND group_code IN ('both', ?)
              AND is_active = 1
            ORDER BY time_start
            """,
            (day, week_type, group),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_session_by_id(session_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM schedule_sessions WHERE id = ?", (session_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_all_sessions() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT * FROM schedule_sessions
            WHERE is_active = 1
            ORDER BY day, time_start
            """
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def add_session(
    day: str,
    week_type: str,
    group_code: str,
    subject: str,
    session_type: str,
    room: str,
    time_start: str,
    time_end: str,
    professor: str,
) -> int:
    async with aiosqlite.connect(_db_path) as db:
        cur = await db.execute(
            """
            INSERT INTO schedule_sessions
                (day, week_type, group_code, subject, session_type,
                 room, time_start, time_end, professor, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (day, week_type, group_code, subject, session_type,
             room, time_start, time_end, professor),
        )
        await db.commit()
        return cur.lastrowid or 0


_VALID_SESSION_FIELDS = frozenset(
    {"day", "week_type", "group_code", "subject", "session_type",
     "room", "time_start", "time_end", "professor", "is_active"}
)


async def update_session(session_id: int, **kwargs: Any) -> None:
    if not kwargs:
        return
    invalid = set(kwargs) - _VALID_SESSION_FIELDS
    if invalid:
        raise ValueError(f"Invalid session field(s): {invalid}")
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [session_id]
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            f"UPDATE schedule_sessions SET {fields} WHERE id = ?", values
        )
        await db.commit()


async def delete_session(session_id: int) -> None:
    """Soft-delete: set is_active = 0."""
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "UPDATE schedule_sessions SET is_active = 0 WHERE id = ?",
            (session_id,),
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------

async def get_attendance_for_session(
    user_id: int, session_id: int, date_str: str
) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT * FROM attendance
            WHERE user_id = ? AND session_id = ? AND date = ?
            """,
            (user_id, session_id, date_str),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


# Alias used in today/mark/edit handlers
async def get_or_create_attendance(
    user_id: int, session_id: int, date_str: str
) -> Optional[Dict[str, Any]]:
    return await get_attendance_for_session(user_id, session_id, date_str)


async def upsert_attendance(
    user_id: int, session_id: int, date_str: str, status: str
) -> None:
    now = _now_iso()
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            """
            INSERT INTO attendance (user_id, session_id, date, status, recorded_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, session_id, date) DO UPDATE SET
                status     = excluded.status,
                updated_at = excluded.updated_at
            """,
            (user_id, session_id, date_str, status, now, now),
        )
        await db.commit()


async def get_attendance_dates(user_id: int) -> List[str]:
    """Return distinct dates (desc) that have recorded attendance."""
    async with aiosqlite.connect(_db_path) as db:
        cur = await db.execute(
            """
            SELECT DISTINCT date FROM attendance
            WHERE user_id = ?
            ORDER BY date DESC
            LIMIT 30
            """,
            (user_id,),
        )
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def get_attendance_stats(user_id: int) -> List[Dict[str, Any]]:
    """Return per-subject/per-type counts."""
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT
                s.subject,
                s.session_type,
                COUNT(*)                                          AS total,
                SUM(CASE WHEN a.status = 'prezent' THEN 1 ELSE 0 END) AS prezente,
                SUM(CASE WHEN a.status = 'absent'  THEN 1 ELSE 0 END) AS absente
            FROM attendance a
            JOIN schedule_sessions s ON a.session_id = s.id
            WHERE a.user_id = ?
            GROUP BY s.subject, s.session_type
            ORDER BY s.subject, s.session_type
            """,
            (user_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_all_attendance_log(user_id: int) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT
                a.date,
                s.day,
                s.time_start,
                s.time_end,
                s.subject,
                s.session_type,
                s.group_code,
                s.room,
                a.status,
                a.recorded_at,
                a.updated_at
            FROM attendance a
            JOIN schedule_sessions s ON a.session_id = s.id
            WHERE a.user_id = ?
            ORDER BY a.date, s.time_start
            """,
            (user_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# User settings
# ---------------------------------------------------------------------------

async def get_user_settings(user_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM user_settings WHERE user_id = ?", (user_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def upsert_user_settings(user_id: int, **kwargs: Any) -> None:
    now = _now_iso()
    existing = await get_user_settings(user_id)
    if existing is None:
        defaults: Dict[str, Any] = {"default_group": "B", "week_override": None}
        defaults.update(kwargs)
        async with aiosqlite.connect(_db_path) as db:
            await db.execute(
                """
                INSERT INTO user_settings (user_id, default_group, week_override, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, defaults["default_group"], defaults.get("week_override"), now),
            )
            await db.commit()
    else:
        existing.update(kwargs)
        existing["updated_at"] = now
        async with aiosqlite.connect(_db_path) as db:
            await db.execute(
                """
                UPDATE user_settings
                SET default_group = :default_group,
                    week_override = :week_override,
                    updated_at    = :updated_at
                WHERE user_id = :user_id
                """,
                existing,
            )
            await db.commit()
