"""
music.py — qo'shiq nomi bo'yicha qidirib, audio (mp3) yuklab olish
bilan bog'liq funksiyalar shu yerda.

Eslatma: faqat BITTA eng mos natija yuklanadi — bu ommaviy musiqa
arxivi emas, oddiy shaxsiy qidiruv vositasi. Iltimos, mualliflik
huquqlariga rioya qiling.
"""

import os
import time
import uuid

from yt_dlp import YoutubeDL

from config import MAX_DOWNLOAD_RETRIES, RETRY_BACKOFF_SECONDS, logger


def search_and_download_music(query: str, out_dir: str) -> tuple[str, str]:
    """Berilgan qo'shiq nomi bo'yicha eng mos natijani topib, mp3 qilib yuklaydi."""
    out_template = os.path.join(out_dir, f"{uuid.uuid4().hex}.%(ext)s")
    ydl_opts = {
        "outtmpl": out_template,
        "format": "bestaudio/best",
        "quiet": True,
        "noplaylist": True,
        "default_search": "ytsearch1",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }
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
    """
    Berilgan (Instagram/TikTok/YouTube va h.k.) video linkidan faqat
    audio (musiqa) qismini mp3 ko'rinishida yuklab oladi. (title, filepath)
    qaytaradi. Qidiruv emas — bevosita shu linkdagi videoning ovozi.
    """
    out_template = os.path.join(out_dir, f"{uuid.uuid4().hex}.%(ext)s")
    ydl_opts = {
        "outtmpl": out_template,
        "format": "bestaudio/best",
        "quiet": True,
        "noplaylist": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }
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
