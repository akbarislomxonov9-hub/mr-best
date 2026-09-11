"""
image_tools.py — rasm (photo) bilan bog'liq funksiyalar:
watermark/belgi tozalash va hajmini siqish.
"""

import os
import time
import uuid

from PIL import Image, ImageDraw
from yt_dlp import YoutubeDL

from config import MAX_DOWNLOAD_RETRIES, RETRY_BACKOFF_SECONDS, logger


def remove_watermark_image(
    input_path: str,
    output_path: str,
    position: str,
    width_ratio: float,
    height_ratio: float,
) -> None:
    """
    Rasmning belgilangan burchagidagi username/watermarkni to'liq qora
    to'rtburchak bilan qoplab yashiradi (video'dagi 'box' rejimi kabi
    kafolatlangan usul).
    """
    img = Image.open(input_path).convert("RGB")
    width, height = img.size
    box_w = int(width * width_ratio)
    box_h = int(height * height_ratio)

    positions = {
        "bottom_left": (0, height - box_h),
        "bottom_right": (width - box_w, height - box_h),
        "top_left": (0, 0),
        "top_right": (width - box_w, 0),
        "none": None,
    }
    if position not in positions:
        raise ValueError(f"Noto'g'ri position: {position}")

    if positions[position] is not None:
        x, y = positions[position]
        draw = ImageDraw.Draw(img)
        draw.rectangle([x, y, x + box_w, y + box_h], fill="black")

    img.save(output_path, quality=95)


def compress_image(input_path: str, output_path: str, quality: int) -> None:
    """Rasm hajmini siqadi (JPEG sifat darajasini pasaytirish orqali)."""
    img = Image.open(input_path).convert("RGB")
    img.save(output_path, format="JPEG", quality=quality, optimize=True)


def resize_image_to_size(input_path: str, output_path: str, target_size: tuple[int, int]) -> None:
    """
    Rasmni berilgan (width, height) o'lchamiga moslaydi: nisbatni
    buzmasdan to'ldiradi va markazdan kesib, aniq talab qilingan
    o'lchamda chiqaradi (Instagram Story/Post kabi qat'iy o'lchamlar
    uchun mos usul — 'cover' rejimi).
    """
    target_w, target_h = target_size
    img = Image.open(input_path).convert("RGB")
    src_w, src_h = img.size

    scale = max(target_w / src_w, target_h / src_h)
    new_w, new_h = int(src_w * scale) + 1, int(src_h * scale) + 1
    img = img.resize((new_w, new_h), Image.LANCZOS)

    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    img = img.crop((left, top, left + target_w, top + target_h))

    img.save(output_path, format="JPEG", quality=92)


def download_image_from_url(url: str, out_dir: str) -> str:
    """
    Link orqali (masalan Instagram rasm posti) rasmni yuklashga urinadi.
    Eslatma: bu — 'best effort' usul, chunki yt-dlp asosan video uchun
    mo'ljallangan. Ba'zi platformalarda ishlamasligi mumkin — bunday
    holda foydalanuvchiga rasmni to'g'ridan-to'g'ri (galereyadan) yuborish
    tavsiya etiladi.
    """
    out_template = os.path.join(out_dir, f"{uuid.uuid4().hex}.%(ext)s")
    ydl_opts = {
        "outtmpl": out_template,
        "quiet": True,
        "noplaylist": True,
        "format": "best",
    }
    last_error: Exception | None = None
    for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filepath = ydl.prepare_filename(info)
                if not os.path.exists(filepath):
                    raise ValueError("Rasm topilmadi (bu link video bo'lishi mumkin).")
                return filepath
        except Exception as e:
            last_error = e
            logger.warning(
                "Rasm yuklashda urinish %s/%s muvaffaqiyatsiz: %s",
                attempt, MAX_DOWNLOAD_RETRIES, e,
            )
            if attempt < MAX_DOWNLOAD_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    assert last_error is not None
    raise last_error
