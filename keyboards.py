"""
keyboards.py — Telegram tugmali menyularini yaratish funksiyalari.
"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from config import (
    MENU_INSTAGRAM,
    MENU_TIKTOK,
    MENU_MUSIC,
    MENU_GALLERY,
    MENU_IMAGE_COMPRESS,
    MENU_VIDEO_COMPRESS,
    MENU_QR,
    MENU_STATS,
    MENU_SETTINGS,
    MENU_TRIM,
    MENU_INFO,
    MENU_QR_SCAN,
    MENU_RESIZE,
)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MENU_INSTAGRAM), KeyboardButton(text=MENU_TIKTOK)],
            [KeyboardButton(text=MENU_MUSIC), KeyboardButton(text=MENU_GALLERY)],
            [KeyboardButton(text=MENU_IMAGE_COMPRESS), KeyboardButton(text=MENU_VIDEO_COMPRESS)],
            [KeyboardButton(text=MENU_TRIM), KeyboardButton(text=MENU_INFO)],
            [KeyboardButton(text=MENU_QR), KeyboardButton(text=MENU_QR_SCAN)],
            [KeyboardButton(text=MENU_RESIZE), KeyboardButton(text=MENU_STATS)],
            [KeyboardButton(text=MENU_SETTINGS)],
        ],
        resize_keyboard=True,
    )
