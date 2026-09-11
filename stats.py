"""
stats.py — botning ishlatilish statistikasini xotirada (RAM) hisoblaydi.

Eslatma: bu statistika faqat bot ishlab turgan vaqt davomida saqlanadi.
Bot qayta ishga tushirilsa (restart), hisoblagichlar nolga tushadi.
Doimiy statistika kerak bo'lsa (masalan SQLite bazasiga yozib), xabar
bering — buni kengaytirib beraman.
"""

import json
import os
from collections import defaultdict

# turi -> soni, masalan: {"video": 12, "musiqa": 5, "rasm": 3}
_counters: dict[str, int] = defaultdict(int)

# Nechta noyob foydalanuvchi botdan foydalangani
_unique_users: set[int] = set()

# Foydalanuvchilar ro'yxati diskka saqlanadi, shunda bot qayta ishga
# tushirilganda ham (masalan avtomatik soatlik xabar yuborish uchun)
# kimlar botdan foydalanganini bilib turadi.
_USERS_FILE = "known_users.json"


def _load_known_users() -> None:
    if os.path.exists(_USERS_FILE):
        try:
            with open(_USERS_FILE, "r", encoding="utf-8") as f:
                _unique_users.update(json.load(f))
        except Exception:
            pass


def _save_known_users() -> None:
    try:
        with open(_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(_unique_users), f)
    except Exception:
        pass


_load_known_users()


def register_user(chat_id: int) -> None:
    """Foydalanuvchini (masalan /start bosganda) ro'yxatga qo'shadi,
    hech qanday amal hisoblanmasa ham (broadcast ro'yxati uchun)."""
    if chat_id not in _unique_users:
        _unique_users.add(chat_id)
        _save_known_users()


def get_known_users() -> set[int]:
    return set(_unique_users)


def record_event(event_type: str, chat_id: int) -> None:
    _counters[event_type] += 1
    if chat_id not in _unique_users:
        _unique_users.add(chat_id)
        _save_known_users()
    else:
        _unique_users.add(chat_id)


def get_stats_text() -> str:
    if not _counters:
        return "📊 Hozircha statistika mavjud emas — birinchi so'rovdan keyin paydo bo'ladi."

    lines = ["📊 Bot statistikasi (joriy ishga tushirilgandan beri):\n"]
    labels = {
        "video": "🎬 Yuklangan videolar",
        "musiqa": "🎵 Yuborilgan musiqalar",
        "rasm": "🖼 Tozalangan rasmlar",
        "rasm_siqish": "🗜 Siqilgan rasmlar",
        "video_siqish": "🎞 Siqilgan videolar",
        "qr": "🔳 Yaratilgan QR-kodlar",
        "video_kesish": "✂️ Kesilgan videolar",
        "info": "ℹ️ So'ralgan video ma'lumotlari",
        "qr_scan": "🔎 O'qilgan QR-kodlar",
        "resize": "📐 O'lchami moslangan rasmlar",
    }
    for key, label in labels.items():
        lines.append(f"{label}: {_counters.get(key, 0)}")

    lines.append(f"\n👥 Noyob foydalanuvchilar: {len(_unique_users)}")
    return "\n".join(lines)
