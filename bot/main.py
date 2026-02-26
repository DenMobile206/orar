"""Bot entry point: load config, init DB, register handlers, start polling."""
from __future__ import annotations

import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

# Add project root to path so `bot.*` imports work when run as `python bot/main.py`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import config_loader, storage
from bot.handlers import admin_schedule, edit, export, mark, settings, start, stats, today

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    config = config_loader.load(config_path)

    token = config["telegram"]["token"]
    if token == "YOUR_BOT_TOKEN_HERE":
        logger.error(
            "Setează token-ul botului în bot/config.yaml (telegram.token)!"
        )
        sys.exit(1)

    db_path = os.path.join(
        os.path.dirname(__file__), config.get("database", {}).get("path", "attendance.db")
    )

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    await storage.init_db(db_path)
    await storage.import_schedule_from_config(config)
    logger.info("Baza de date inițializată: %s", db_path)

    # ------------------------------------------------------------------
    # Bot + Dispatcher
    # ------------------------------------------------------------------
    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Register routers in priority order (more-specific first)
    dp.include_router(start.router)
    dp.include_router(today.router)
    dp.include_router(mark.router)
    dp.include_router(edit.router)
    dp.include_router(stats.router)
    dp.include_router(export.router)
    dp.include_router(settings.router)
    dp.include_router(admin_schedule.router)

    logger.info("Bot pornit. Ascult mesaje…")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        logger.info("Bot oprit.")


if __name__ == "__main__":
    asyncio.run(main())
