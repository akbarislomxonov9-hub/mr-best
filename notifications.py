"""
notifications.py — media yuborilgandan keyin foydalanuvchiga
do'stona eslatma xabari yuborish bilan bog'liq funksiyalar.
"""

import asyncio
import random

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from config import FOLLOWUP_DELAY_SECONDS, FOLLOWUP_MESSAGES, logger


async def send_followup_reminder(bot: Bot, chat_id: int) -> None:
    await asyncio.sleep(FOLLOWUP_DELAY_SECONDS)
    try:
        await bot.send_message(chat_id, random.choice(FOLLOWUP_MESSAGES))
    except TelegramAPIError as e:
        logger.info(
            "Follow-up yuborilmadi (foydalanuvchi botni bloklagan bo'lishi mumkin): %s", e
        )
    except Exception:
        logger.exception("Follow-up eslatma yuborishda kutilmagan xatolik")


def schedule_followup(bot: Bot, chat_id: int) -> None:
    asyncio.create_task(send_followup_reminder(bot, chat_id))
