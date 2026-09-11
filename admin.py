"""
admin.py — admin panel (broadcast) va barcha foydalanuvchilarga
avtomatik soatlik xabar yuborish tizimi.
"""

import asyncio
import random

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError

from config import (
    ADMIN_IDS,
    HOURLY_BROADCAST_ENABLED,
    HOURLY_BROADCAST_INTERVAL_SECONDS,
    HOURLY_BROADCAST_MESSAGES,
    logger,
)
import stats


def is_admin(chat_id: int) -> bool:
    return chat_id in ADMIN_IDS


async def broadcast_message(bot: Bot, text: str) -> tuple[int, int]:
    """
    Barcha ma'lum foydalanuvchilarga xabar yuboradi.
    Qaytaradi: (muvaffaqiyatli yuborilganlar soni, xato bo'lganlar soni)
    """
    users = stats.get_known_users()
    success, failed = 0, 0
    for chat_id in users:
        try:
            await bot.send_message(chat_id, text)
            success += 1
        except TelegramForbiddenError:
            # Foydalanuvchi botni bloklagan — xato hisoblanmaydi, shunchaki o'tkazib yuboriladi
            failed += 1
        except TelegramAPIError as e:
            logger.info("Broadcast xatosi (chat_id=%s): %s", chat_id, e)
            failed += 1
        # Telegram flood-limitiga tushib qolmaslik uchun kichik pauza
        await asyncio.sleep(0.05)
    return success, failed


async def hourly_broadcast_loop(bot: Bot) -> None:
    """
    Fon vazifasi (background task): har HOURLY_BROADCAST_INTERVAL_SECONDS
    soniyada barcha foydalanuvchilarga tasodifiy maslahat/bildirishnoma
    xabarini yuboradi. bot.py ichida asyncio.create_task() bilan
    ishga tushiriladi.
    """
    if not HOURLY_BROADCAST_ENABLED:
        return

    logger.info("Soatlik avtomatik xabar tizimi ishga tushdi.")
    while True:
        await asyncio.sleep(HOURLY_BROADCAST_INTERVAL_SECONDS)
        message = random.choice(HOURLY_BROADCAST_MESSAGES)
        try:
            success, failed = await broadcast_message(bot, message)
            logger.info(
                "Soatlik xabar yuborildi: %s ta muvaffaqiyatli, %s ta xato.",
                success, failed,
            )
        except Exception:
            logger.exception("Soatlik xabar yuborishda kutilmagan xatolik")
