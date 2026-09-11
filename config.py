"""
config.py — barcha sozlamalar va loglash shu yerda.
Boshqa fayllar shu moduldan sozlamalarni import qiladi.
"""

import logging
import logging.handlers
import os
import re

from dotenv import load_dotenv

# ------------------------------------------------------------------
# .env FAYLIDAN O'QISH
# ------------------------------------------------------------------

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN topilmadi! Loyiha papkasida .env fayl yarating:\n"
        "BOT_TOKEN=sizning_tokeningiz"
    )

# .env faylida ADMIN_IDS=123456789,987654321 shaklida vergul bilan
# ajratilgan Telegram user ID'larni yozing (broadcast buyrug'i uchun).
_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: set[int] = {
    int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip().isdigit()
}

# ------------------------------------------------------------------
# WATERMARK SOZLAMALARI
# ------------------------------------------------------------------

WATERMARK_POSITION = "bottom_left"   # bottom_left / bottom_right / top_left / top_right / none
WATERMARK_MODE = "box"               # "box" (kafolatlangan) yoki "blur"
WATERMARK_WIDTH_RATIO = 0.40
WATERMARK_HEIGHT_RATIO = 0.14

# --- Rasm siqish sozlamalari ---
IMAGE_COMPRESS_QUALITY = 60      # 1-95, past qiymat = kichikroq fayl, past sifat

# --- Video siqish sozlamalari ---
VIDEO_COMPRESS_CRF = 30          # 18-35, katta qiymat = kichikroq fayl, past sifat

# ------------------------------------------------------------------
# BILDIRISHNOMA SOZLAMALARI
# ------------------------------------------------------------------

FOLLOWUP_DELAY_SECONDS = 60 * 60  # 1 soat
FOLLOWUP_MESSAGES = [
    "🙂 Salom! Yana biror video yoki qo'shiq kerak bo'lsa, shu yerdaman.",
    "🎧 Yangi musiqa kerakmi? Nomini yuboring, topib beraman.",
    "📥 Yana biror video yuklab olmoqchimisiz?",
    "👋 Ishlaringiz yaxshimi? Kerak bo'lsa yana buyurtma bering.",
]

# --- Barcha foydalanuvchilarga yuboriladigan avtomatik soatlik xabar ---
HOURLY_BROADCAST_ENABLED = True
HOURLY_BROADCAST_INTERVAL_SECONDS = 60 * 60  # 1 soat
HOURLY_BROADCAST_MESSAGES = [
    "💡 Bilasizmi? Video linkini yuborsangiz, men avtomatik watermarkni tozalayman.",
    "🎵 Qo'shiq nomini yozib yuboring — men uni qidirib, mp3 qilib beraman.",
    "✂️ Videoni kesish (trim) funksiyasi orqali faqat kerakli qismini olishingiz mumkin.",
    "📐 Rasm o'lchamini Instagram Story yoki Post uchun moslashtirib beraman.",
    "🔎 QR-kod rasmini yuborsangiz, ichidagi matn/linkni o'qib beraman.",
    "🗜 Fayl hajmi katta bo'lsa, 🗜 Rasm siqish / 🎞 Video siqish bo'limidan foydalaning.",
    "ℹ️ Videoni yuklamasdan turib ma'lumot (muallif, davomiylik) olishingiz mumkin.",
    "📊 /help buyrug'i orqali barcha imkoniyatlar ro'yxatini ko'rishingiz mumkin.",
]

# ------------------------------------------------------------------
# PRO SOZLAMALAR
# ------------------------------------------------------------------

MAX_VIDEO_DURATION_SECONDS = 10 * 60   # 10 daqiqadan uzun video qabul qilinmaydi
MAX_DOWNLOAD_RETRIES = 3               # yuklashda necha marta qayta urinish
RETRY_BACKOFF_SECONDS = 2              # har urinish orasidagi kutish (ortib boradi)
USER_COOLDOWN_SECONDS = 5              # bitta foydalanuvchi so'rovlari orasidagi minimal vaqt

# --- Rasm o'lchamlari (resize) tayyor shablonlari: nom -> (width, height) ---
IMAGE_RESIZE_PRESETS: dict[str, tuple[int, int]] = {
    "story": (1080, 1920),
    "post": (1080, 1350),
    "square": (1080, 1080),
    "thumbnail": (1280, 720),
}

# ------------------------------------------------------------------
# LINK ANIQLAGICHLAR
# ------------------------------------------------------------------

# Istalgan http(s) link — yt-dlp 1000dan ortiq saytni qo'llab-quvvatlaydi,
# shuning uchun har bir sayt uchun alohida regex yozish shart emas.
GENERIC_URL_RE = re.compile(r"https?://\S+")

PLATFORM_NAMES = {
    "instagram.com": "Instagram",
    "tiktok.com": "TikTok",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "facebook.com": "Facebook",
    "fb.watch": "Facebook",
    "twitter.com": "Twitter/X",
    "x.com": "Twitter/X",
    "likee.video": "Likee",
    "pinterest.com": "Pinterest",
    "vimeo.com": "Vimeo",
    "snapchat.com": "Snapchat",
}


def detect_platform_name(url: str) -> str:
    for domain, name in PLATFORM_NAMES.items():
        if domain in url:
            return name
    return "Video"


def extract_url(text: str, pattern: re.Pattern) -> str | None:
    match = pattern.search(text)
    return match.group(0) if match else None


# ------------------------------------------------------------------
# MENYU MATNLARI
# ------------------------------------------------------------------

MENU_INSTAGRAM = "📥 Instagram"
MENU_TIKTOK = "🎬 TikTok"
MENU_MUSIC = "🎵 Musiqa"
MENU_GALLERY = "🖼 Galereya video"
MENU_IMAGE_COMPRESS = "🗜 Rasm siqish"
MENU_VIDEO_COMPRESS = "🎞 Video siqish"
MENU_QR = "🔳 QR-kod yaratish"
MENU_STATS = "📊 Statistika"
MENU_SETTINGS = "⚙️ Sozlamalar"

# --- Yangi bo'limlar (5 ta qo'shimcha funksiya) ---
MENU_TRIM = "✂️ Video kesish"
MENU_INFO = "ℹ️ Video ma'lumoti"
MENU_QR_SCAN = "🔎 QR o'qish"
MENU_RESIZE = "📐 Rasm o'lchami"

# ------------------------------------------------------------------
# LOGLASH (professional: fayl + konsol, aylanma fayllar)
# ------------------------------------------------------------------

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "bot.log")

os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("instabot")
logger.setLevel(logging.INFO)

_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_formatter)

# 5 MB dan oshsa yangi faylga o'tadi, oxirgi 5 ta faylni saqlaydi
_file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
_file_handler.setFormatter(_formatter)

logger.addHandler(_console_handler)
logger.addHandler(_file_handler)

# aiogram'ning ortiqcha "debug" xabarlarini kamaytiramiz
logging.getLogger("aiogram").setLevel(logging.WARNING)
