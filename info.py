"""
info.py — video linkini yuklamasdan turib uning haqida ma'lumot
(sarlavha, muallif, davomiylik, ko'rishlar soni) olish.
"""

import html
import time

from yt_dlp import YoutubeDL

from config import MAX_DOWNLOAD_RETRIES, RETRY_BACKOFF_SECONDS, logger


def _format_duration(seconds: int | float | None) -> str:
    if not seconds:
        return "Noma'lum"
    seconds = int(seconds)
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{sec:02d}"
    return f"{minutes}:{sec:02d}"


def _format_count(n: int | None) -> str:
    if n is None:
        return "Noma'lum"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}ming"
    return str(n)


def get_media_info(url: str) -> dict:
    """
    Linkni yuklamasdan (download=False) faqat meta-ma'lumotini oladi.
    Qaytaradi: title, uploader, duration_text, view_count_text,
    like_count_text, thumbnail (URL yoki None), webpage_url.
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
    }
    last_error: Exception | None = None
    for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    "title": info.get("title") or "Noma'lum sarlavha",
                    "uploader": info.get("uploader") or info.get("channel") or "Noma'lum",
                    "duration_text": _format_duration(info.get("duration")),
                    "view_count_text": _format_count(info.get("view_count")),
                    "like_count_text": _format_count(info.get("like_count")),
                    "thumbnail": info.get("thumbnail"),
                    "webpage_url": info.get("webpage_url") or url,
                    "extractor": info.get("extractor_key") or info.get("extractor") or "Noma'lum",
                }
        except Exception as e:
            last_error = e
            logger.warning(
                "Ma'lumot olishda urinish %s/%s muvaffaqiyatsiz: %s",
                attempt, MAX_DOWNLOAD_RETRIES, e,
            )
            if attempt < MAX_DOWNLOAD_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    assert last_error is not None
    raise last_error


def format_info_message(info: dict) -> str:
    # Sarlavha/muallif kabi maydonlar tashqi manbadan (video platformasidan)
    # kelgani uchun HTML maxsus belgilarini (<, >, &) ekranlashtiramiz —
    # aks holda Telegram HTML parse_mode xabarni rad etishi mumkin.
    title = html.escape(str(info["title"]))
    uploader = html.escape(str(info["uploader"]))
    extractor = html.escape(str(info["extractor"]))
    url = html.escape(str(info["webpage_url"]))

    return (
        f"ℹ️ <b>{title}</b>\n\n"
        f"👤 Muallif: {uploader}\n"
        f"⏱ Davomiyligi: {info['duration_text']}\n"
        f"👁 Ko'rishlar: {info['view_count_text']}\n"
        f"❤️ Layklar: {info['like_count_text']}\n"
        f"🌐 Manba: {extractor}\n"
        f"🔗 {url}"
    )
