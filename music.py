"""
music.py — qo'shiq nomi bo'yicha qidirib, audio (mp3) yuklab olish
"""

import os
import time
import uuid

from yt_dlp import YoutubeDL

from config import MAX_DOWNLOAD_RETRIES, RETRY_BACKOFF_SECONDS, logger

COOKIE_FILE = r"C:\Users\user\Downloads\akow1\cookies.txt"


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
    }
    if use_cookies and os.path.isfile(COOKIE_FILE):
        opts["cookiefile"] = COOKIE_FILE
    return opts


def _needs_cookies(url: str) -> bool:
    u = url.lower()
    return any(x in u for x in (
        "instagram.com",
        "facebook.com",
        "fb.watch",
        "tiktok.com",
    ))


def search_and_download_music(query: str, out_dir: str) -> tuple[str, str]:
    """Qo'shiq nomi bo'yicha YouTube'dan TO'LIQ trek yuklaydi."""
    out_template = os.path.join(out_dir, f"{uuid.uuid4().hex}.%(ext)s")
    ydl_opts = _base_ydl_opts(out_template, use_cookies=False)
    ydl_opts["default_search"] = "ytsearch1"

    last_error: Exception | None = None
    for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=True)
                if "entries" in info:
                    if not info["entries"]:
                        raise ValueError("Hech qanday natija topilmadi.")
                    info = info["entries"][0]
                title = info.get("title", query)
                filepath = os.path.splitext(ydl.prepare_filename(info))[0] + ".mp3"
                return title, filepath
        except Exception as e:
            last_error = e
            logger.warning(
                "Musiqa qidirishda urinish %s/%s muvaffaqiyatsiz: %s",
                attempt, MAX_DOWNLOAD_RETRIES, e,
            )
            if attempt < MAX_DOWNLOAD_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    assert last_error is not None
    raise last_error


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