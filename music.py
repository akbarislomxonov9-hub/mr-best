"""
music.py — qo'shiq nomi bo'yicha qidirib, audio (mp3) yuklab olish
YouTube bloklansa (bot tekshiruvi), avtomatik SoundCloud'ga o'tadi.
"""

import os
import shutil
import time
import uuid

from yt_dlp import YoutubeDL

from config import MAX_DOWNLOAD_RETRIES, RETRY_BACKOFF_SECONDS, logger

# Cookies fayl manzillari (birinchi topilgani ishlatiladi):
# 1) Render "Secret Files" (tavsiya etiladi, GitHub'ga yuklanmaydi)
# 2) loyiha ildizidagi cookies.txt
COOKIE_SOURCES = ["/etc/secrets/cookies.txt", "cookies.txt"]
COOKIE_COPY = "/tmp/cookies_copy.txt"  # Secret Files faqat o'qish uchun, shuning uchun nusxa


def _get_cookiefile() -> str | None:
    for src in COOKIE_SOURCES:
        if os.path.isfile(src):
            try:
                shutil.copyfile(src, COOKIE_COPY)
                return COOKIE_COPY
            except OSError:
                return src
    return None


def _needs_cookies(url: str) -> bool:
    u = url.lower()
    return "youtube.com" in u or "youtu.be" in u


def _base_ydl_opts(out_template: str, use_cookies: bool = False) -> dict:
    opts = {
        "outtmpl": out_template,
        "format": "bestaudio/best",
        "quiet": True,
        "noplaylist": True,
        "noprogress": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        },
    }
    if use_cookies:
        cookiefile = _get_cookiefile()
        if cookiefile:
            opts["cookiefile"] = cookiefile
    return opts


def _is_bot_block(error: Exception) -> bool:
    text = str(error).lower()
    return "confirm you" in text and "bot" in text or "sign in" in text


def _search_once(search_prefix: str, query: str, out_dir: str, use_cookies: bool) -> tuple[str, str]:
    out_template = os.path.join(out_dir, f"{uuid.uuid4().hex}.%(ext)s")
    ydl_opts = _base_ydl_opts(out_template, use_cookies=use_cookies)
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"{search_prefix}:{query}", download=True)
        if "entries" in info:
            if not info["entries"]:
                raise ValueError("Hech qanday natija topilmadi.")
            info = info["entries"][0]
        title = info.get("title", query)
        filepath = os.path.splitext(ydl.prepare_filename(info))[0] + ".mp3"
        if not os.path.exists(filepath):
            raise FileNotFoundError("Audio fayl yaratilmadi.")
        return title, filepath


def search_and_download_music(query: str, out_dir: str) -> tuple[str, str]:
    """Avval YouTube, bloklansa yoki topilmasa SoundCloud'dan yuklaydi."""
    sources = [
        ("YouTube", "ytsearch1", True),
        ("SoundCloud", "scsearch1", False),
    ]
    errors: list[str] = []

    for name, prefix, use_cookies in sources:
        for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
            try:
                return _search_once(prefix, query, out_dir, use_cookies)
            except Exception as e:
                logger.warning(
                    "%s: urinish %s/%s muvaffaqiyatsiz: %s",
                    name, attempt, MAX_DOWNLOAD_RETRIES, e,
                )
                # Bot bloki bo'lsa qayta urinish befoyda, darhol keyingi manbaga o'tamiz
                if _is_bot_block(e) or attempt == MAX_DOWNLOAD_RETRIES:
                    errors.append(f"{name}: {str(e)[:120]}")
                    break
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)

    raise RuntimeError(" | ".join(errors))


def download_audio_from_url(url: str, out_dir: str) -> tuple[str, str]:
    out_template = os.path.join(out_dir, f"{uuid.uuid4().hex}.%(ext)s")
    ydl_opts = _base_ydl_opts(out_template, use_cookies=_needs_cookies(url))

    last_error: Exception | None = None
    for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "audio")
                filepath = os.path.splitext(ydl.prepare_filename(info))[0] + ".mp3"
                return title, filepath
        except Exception as e:
            last_error = e
            logger.warning(
                "Audio yuklashda urinish %s/%s muvaffaqiyatsiz: %s",
                attempt, MAX_DOWNLOAD_RETRIES, e,
            )
            if attempt < MAX_DOWNLOAD_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    assert last_error is not None
    raise last_error