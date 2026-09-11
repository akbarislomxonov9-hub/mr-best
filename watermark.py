"""
watermark.py — video yuklab olish (yt-dlp) va watermark/username
hududini tozalash (ffmpeg) bilan bog'liq barcha funksiyalar shu yerda.
"""

import os
import shutil
import subprocess
import time

from yt_dlp import YoutubeDL

from config import (
    MAX_VIDEO_DURATION_SECONDS,
    MAX_DOWNLOAD_RETRIES,
    RETRY_BACKOFF_SECONDS,
    WATERMARK_WIDTH_RATIO,
    WATERMARK_HEIGHT_RATIO,
    logger,
)


def _download_video_once(url: str, out_dir: str) -> str:
    out_template = os.path.join(out_dir, "%(id)s.%(ext)s")
    ydl_opts = {
        "outtmpl": out_template,
        "format": "mp4/best",
        "quiet": True,
        "noplaylist": True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        # Avval faqat metama'lumotni olamiz (tarmoqqa 2 marta so'rov
        # yubormaslik uchun), davomiylikni tekshiramiz, so'ng shu bir xil
        # ma'lumot asosida yuklab olamiz.
        info = ydl.extract_info(url, download=False)
        duration = info.get("duration") or 0
        if duration and duration > MAX_VIDEO_DURATION_SECONDS:
            raise ValueError(
                f"Video juda uzun ({duration // 60} daqiqa). "
                f"Maksimal ruxsat etilgan: {MAX_VIDEO_DURATION_SECONDS // 60} daqiqa."
            )
        ydl.download([url])
        filepath = ydl.prepare_filename(info)
        if not os.path.exists(filepath):
            # Ba'zi platformalarda kengaytma mos kelmasligi mumkin (masalan
            # .webm o'rniga .mp4 saqlangan bo'lishi mumkin) — papkadagi eng
            # so'nggi yaratilgan faylni topamiz.
            base_dir = os.path.dirname(filepath) or out_dir
            candidates = [
                os.path.join(base_dir, f) for f in os.listdir(base_dir)
            ]
            candidates = [f for f in candidates if os.path.isfile(f)]
            if candidates:
                filepath = max(candidates, key=os.path.getmtime)
        return filepath


def download_video(url: str, out_dir: str) -> str:
    """
    yt-dlp yordamida videoni yuklaydi. Tarmoq xatosi bo'lsa
    MAX_DOWNLOAD_RETRIES marta qayta urinadi (backoff bilan).
    """
    last_error: Exception | None = None
    for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
        try:
            return _download_video_once(url, out_dir)
        except ValueError:
            raise  # davomiylik chegarasi — qayta urinish shart emas
        except Exception as e:
            last_error = e
            logger.warning(
                "Yuklashda urinish %s/%s muvaffaqiyatsiz: %s",
                attempt, MAX_DOWNLOAD_RETRIES, e,
            )
            if attempt < MAX_DOWNLOAD_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    assert last_error is not None
    raise last_error


def get_video_resolution(filepath: str) -> tuple[int, int]:
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        filepath,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    width_str, height_str = result.stdout.strip().split("x")
    return int(width_str), int(height_str)


def remove_watermark(input_path: str, output_path: str, position: str, mode: str) -> None:
    """
    Videoning belgilangan burchagidagi username/watermarkni yo'q qiladi.

    mode == "box"  -> hududni to'liq qora to'rtburchak bilan qoplaydi
                       (100% kafolatlangan yashirish).
    mode == "blur" -> hududni kuchli boxblur bilan xiralashtiradi.
    """
    if position == "none":
        shutil.copyfile(input_path, output_path)
        return

    width, height = get_video_resolution(input_path)
    box_w = int(width * WATERMARK_WIDTH_RATIO)
    box_h = int(height * WATERMARK_HEIGHT_RATIO)

    positions = {
        "bottom_left": (0, height - box_h),
        "bottom_right": (width - box_w, height - box_h),
        "top_left": (0, 0),
        "top_right": (width - box_w, 0),
    }
    if position not in positions:
        raise ValueError(f"Noto'g'ri position: {position}")
    x, y = positions[position]

    if mode == "box":
        vf = f"drawbox=x={x}:y={y}:w={box_w}:h={box_h}:color=black@1.0:t=fill"
        cmd = ["ffmpeg", "-y", "-i", input_path, "-vf", vf, "-c:a", "copy", output_path]
    elif mode == "blur":
        filter_complex = (
            f"[0:v]split=2[base][blur_src];"
            f"[blur_src]crop={box_w}:{box_h}:{x}:{y},"
            f"boxblur=40:10:enable=1,boxblur=40:10:enable=1[blurred];"
            f"[base][blurred]overlay={x}:{y}[out]"
        )
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-filter_complex", filter_complex,
            "-map", "[out]", "-map", "0:a?", "-c:a", "copy",
            output_path,
        ]
    else:
        raise ValueError(f"Noto'g'ri mode: {mode}")

    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg xatoligi: {result.stderr.decode(errors='ignore')[:500]}")


def extract_audio_from_local_video(input_path: str, output_path: str) -> None:
    """
    Allaqachon diskda mavjud bo'lgan video faylning audio (musiqa)
    qismini mp3 ko'rinishida ajratib oladi. (Galereyadan yuborilgan
    video uchun ishlatiladi — internetdan qayta yuklash shart emas.)
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vn",                 # video oqimini olib tashlaymiz
        "-acodec", "libmp3lame",
        "-ab", "192k",
        "-ar", "44100",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg xatoligi: {result.stderr.decode(errors='ignore')[:500]}")


def get_video_duration(filepath: str) -> float:
    """Video davomiyligini soniyalarda qaytaradi."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        filepath,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def trim_video(input_path: str, output_path: str, start_seconds: float, end_seconds: float) -> None:
    """
    Videoning [start_seconds, end_seconds] oralig'ini kesib oladi.
    '-c copy' bilan tez (qayta kodlashsiz) kesishga urinadi; agar bu
    ishlamasa (ba'zi formatlarda kalit-freym muammosi bo'lishi mumkin),
    qayta kodlash bilan takrorlaydi.
    """
    if end_seconds <= start_seconds:
        raise ValueError("Tugash vaqti boshlanish vaqtidan katta bo'lishi kerak.")

    duration = round(end_seconds - start_seconds, 3)

    fast_cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_seconds),
        "-i", input_path,
        "-t", str(duration),
        "-c", "copy",
        output_path,
    ]
    result = subprocess.run(fast_cmd, capture_output=True)
    if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return

    # Tez usul ishlamasa — qayta kodlash bilan aniqroq kesamiz
    accurate_cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-ss", str(start_seconds),
        "-t", str(duration),
        "-vcodec", "libx264",
        "-acodec", "aac",
        output_path,
    ]
    result = subprocess.run(accurate_cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg xatoligi: {result.stderr.decode(errors='ignore')[:500]}")


def compress_video(input_path: str, output_path: str, crf: int) -> None:
    """
    Video hajmini kichraytiradi (H.264 CRF siqish orqali).
    CRF qancha katta bo'lsa, fayl shuncha kichik, lekin sifat shuncha past.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vcodec", "libx264",
        "-crf", str(crf),
        "-preset", "faster",
        "-acodec", "aac",
        "-b:a", "128k",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg xatoligi: {result.stderr.decode(errors='ignore')[:500]}")
