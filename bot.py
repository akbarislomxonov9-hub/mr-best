
 

import asyncio
import os
import tempfile
import time
import uuid

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    FSInputFile,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import CommandStart, Command
from aiogram.exceptions import TelegramAPIError

from aiogram.types import ErrorEvent

from config import (
    BOT_TOKEN,
    WATERMARK_POSITION,
    WATERMARK_MODE,
    WATERMARK_WIDTH_RATIO,
    WATERMARK_HEIGHT_RATIO,
    IMAGE_COMPRESS_QUALITY,
    VIDEO_COMPRESS_CRF,
    MAX_VIDEO_DURATION_SECONDS,
    USER_COOLDOWN_SECONDS,
    GENERIC_URL_RE,
    IMAGE_RESIZE_PRESETS,
    extract_url,
    detect_platform_name,
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
    FOLLOWUP_DELAY_SECONDS,
    logger,
)
from keyboards import main_menu_keyboard
from watermark import (
    download_video,
    remove_watermark,
    extract_audio_from_local_video,
    compress_video,
    trim_video,
    get_video_duration,
)
from music import search_and_download_music, download_audio_from_url
from image_tools import (
    remove_watermark_image,
    compress_image,
    download_image_from_url,
    resize_image_to_size,
)
from qr_tools import generate_qr_code, decode_qr_code
from info import get_media_info, format_info_message
from notifications import schedule_followup
import admin
import stats

# ==================================================================
# BOT OB'EKTLARI VA HOLAT
# ==================================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_mode: dict[int, str | None] = {}
user_last_request: dict[int, float] = {}

# Foydalanuvchi link yoki video yuborgach, "musiqa yoki video?" deb
# so'ralganda, javob kelgunicha shu yerda kutib turadi.
# chat_id -> {"kind": "link", "url": ..., "platform": ...}
#          | {"kind": "video", "file_id": ...}
pending_choice: dict[int, dict] = {}

# ✂️ Video kesish (trim) uchun: chat_id -> yuklab olingan videoning
# diskdagi (vaqtinchalik bo'lmagan) yo'li. Foydalanuvchi "boshlanish-tugash"
# vaqtini yozganda ishlatiladi.
trim_pending: dict[int, str] = {}

# 📐 Rasm o'lchamini moslash uchun: chat_id -> yuklab olingan rasm yo'li
resize_pending: dict[int, str] = {}

TRIM_DIR = "downloads/trim"
RESIZE_DIR = "downloads/resize"
os.makedirs(TRIM_DIR, exist_ok=True)
os.makedirs(RESIZE_DIR, exist_ok=True)


def choice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="🎵 Musiqa (audio)", callback_data="choice:music"),
            InlineKeyboardButton(text="🖼 Video (watermark tozalangan)", callback_data="choice:video"),
        ]]
    )


_RESIZE_LABELS = {
    "story": "📱 Story (1080x1920)",
    "post": "🖼 Post (1080x1350)",
    "square": "⬜ Kvadrat (1080x1080)",
    "thumbnail": "🖥 Thumbnail (1280x720)",
}


def resize_preset_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=_RESIZE_LABELS[key], callback_data=f"resize:{key}")]
        for key in IMAGE_RESIZE_PRESETS
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def check_cooldown(chat_id: int) -> float:
    """
    Agar foydalanuvchi juda tez-tez so'rov yuborayotgan bo'lsa,
    kutish kerak bo'lgan soniyalar sonini qaytaradi (0 bo'lsa — bemalol).
    """
    now = time.monotonic()
    last = user_last_request.get(chat_id, 0.0)
    elapsed = now - last
    if elapsed < USER_COOLDOWN_SECONDS:
        return round(USER_COOLDOWN_SECONDS - elapsed, 1)
    user_last_request[chat_id] = now
    return 0.0


# ==================================================================
# BUYRUQLAR
# ==================================================================

@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user_mode[message.chat.id] = None
    stats.register_user(message.chat.id)
    logger.info("Foydalanuvchi %s /start bosdi", message.chat.id)
    await message.answer(
        "Salom! 👋 Xush kelibsiz!\n\n"
        "Men ko'p funksiyali media botman — video, musiqa va rasmlar bilan "
        "bog'liq turli vazifalarni bajaraman. Quyida nima qila olishimni "
        "batafsil tushuntiraman:\n\n"
        f"{MENU_INSTAGRAM} — Instagram post/reels linkini yuboring, video "
        "yuklab, undagi username/watermarkni tozalayman.\n\n"
        f"{MENU_TIKTOK} — TikTok video linkini yuboring, xuddi shunday "
        "watermarkni tozalayman.\n\n"
        f"{MENU_MUSIC} — qo'shiq nomini yozing (masalan 'Ummon guruhi - "
        "Ohangim'), men uni qidirib, audio fayl sifatida yuboraman.\n\n"
        f"{MENU_GALLERY} — telefon/kompyuteringizdagi videoni to'g'ridan-"
        "to'g'ri yuboring, undagi belgini tozalab beraman.\n\n"
        "🖼 Rasm — istalgan rasmni (fayl sifatida) yuborsangiz, undagi "
        "watermark/belgini ham tozalayman.\n\n"
        f"{MENU_IMAGE_COMPRESS} — rasm hajmini kichraytirish (fayl hajmi "
        "katta bo'lsa foydali).\n\n"
        f"{MENU_VIDEO_COMPRESS} — video hajmini kichraytirish.\n\n"
        f"{MENU_TRIM} — videoning faqat kerakli qismini (masalan 5-15-"
        "soniyalarini) kesib olaman.\n\n"
        f"{MENU_INFO} — video linkini yuklamasdan turib, uning sarlavhasi, "
        "muallifi va davomiyligini ko'rsataman.\n\n"
        f"{MENU_QR} — istalgan matn yoki linkdan QR-kod yaratib beraman.\n\n"
        f"{MENU_QR_SCAN} — rasmdagi QR-kodni o'qib, ichidagi matn/linkni "
        "chiqarib beraman.\n\n"
        f"{MENU_RESIZE} — rasmni Instagram Story/Post/Kvadrat o'lchamiga "
        "moslashtiraman.\n\n"
        f"{MENU_STATS} — botning qancha ishlaganini ko'rsataman.\n\n"
        f"{MENU_SETTINGS} — joriy sozlamalarni ko'rsataman.\n\n"
        "💡 Eslatma: Instagram/TikTok'dan tashqari, YouTube, Facebook, "
        "Twitter/X va boshqa ko'plab tarmoqlardan ham link yuborsangiz, "
        "avtomatik aniqlab ishlov beraman.\n\n"
        "Yordam kerak bo'lsa istalgan vaqtda /help yozing. Boshladik! 🚀",
        reply_markup=main_menu_keyboard(),
    )


@dp.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "🆘 Yordam\n\n"
        "• Video link (Instagram, TikTok, YouTube, Facebook, Twitter/X va h.k.) "
        "yuborsangiz, bot 🎵 Musiqa yoki 🖼 Video (watermark tozalangan) "
        "kerakligini so'raydi.\n"
        "• Video faylni to'g'ridan-to'g'ri (galereyadan) yuborsangiz ham, "
        "xuddi shu tanlov beriladi.\n"
        "• Rasm yuborsangiz, undagi watermark/belgi avtomatik tozalanadi.\n"
        "• Qo'shiq nomi bo'yicha qidirish uchun 🎵 Musiqa tugmasini bosing.\n"
        "• 🗜 Rasm siqish / 🎞 Video siqish — fayl hajmini kichraytiradi.\n"
        "• ✂️ Video kesish — video yuboring, so'ng oralig'ini yozing "
        "(masalan: 5-15).\n"
        "• ℹ️ Video ma'lumoti — linkni yuboring, yuklamasdan ma'lumot beraman.\n"
        "• 🔳 QR-kod yaratish — istalgan matn/linkdan QR-kod yaratadi.\n"
        "• 🔎 QR o'qish — QR-kodli rasm yuboring, ichidagi matnni o'qiyman.\n"
        "• 📐 Rasm o'lchami — rasmni Story/Post/Kvadrat o'lchamiga moslayman.\n"
        "• 📊 Statistika — botning ishlatilish hisobini ko'rsatadi.\n"
        f"• Video davomiyligi {MAX_VIDEO_DURATION_SECONDS // 60} daqiqadan oshmasligi kerak.\n"
        "• Joriy amalni bekor qilish uchun /cancel yozing."
    )


@dp.message(Command("cancel"))
async def cmd_cancel(message: Message) -> None:
    chat_id = message.chat.id
    user_mode[chat_id] = None
    pending_choice.pop(chat_id, None)

    old_trim_file = trim_pending.pop(chat_id, None)
    if old_trim_file and os.path.exists(old_trim_file):
        try:
            os.remove(old_trim_file)
        except OSError:
            pass

    old_resize_file = resize_pending.pop(chat_id, None)
    if old_resize_file and os.path.exists(old_resize_file):
        try:
            os.remove(old_resize_file)
        except OSError:
            pass

    await message.answer("❌ Bekor qilindi. Bosh menyuga qaytdingiz.", reply_markup=main_menu_keyboard())


@dp.message(Command("broadcast"))
async def cmd_broadcast(message: Message) -> None:
    """Faqat admin uchun: barcha foydalanuvchilarga xabar yuboradi.
    Foydalanish: /broadcast Xabar matni shu yerda"""
    chat_id = message.chat.id
    if not admin.is_admin(chat_id):
        await message.answer("⛔ Bu buyruq faqat admin uchun.")
        return

    text = (message.text or "").split(maxsplit=1)
    if len(text) < 2 or not text[1].strip():
        await message.answer("✍️ Foydalanish: /broadcast Xabar matni shu yerda")
        return

    broadcast_text = text[1].strip()
    await message.answer("📢 Xabar yuborilmoqda...")
    success, failed = await admin.broadcast_message(bot, broadcast_text)
    await message.answer(
        f"✅ Yuborildi!\n👥 Muvaffaqiyatli: {success}\n⚠️ Yetib bormadi: {failed}"
    )


@dp.message(F.text == MENU_INSTAGRAM)
async def menu_instagram(message: Message) -> None:
    user_mode[message.chat.id] = "instagram"
    await message.answer("📥 Instagram post yoki reels linkini yuboring.")


@dp.message(F.text == MENU_TIKTOK)
async def menu_tiktok(message: Message) -> None:
    user_mode[message.chat.id] = "tiktok"
    await message.answer("🎬 TikTok video linkini yuboring.")


@dp.message(F.text == MENU_MUSIC)
async def menu_music(message: Message) -> None:
    user_mode[message.chat.id] = "music"
    await message.answer("🎵 Qo'shiq nomini (va ijrochisini) yozing, masalan: 'Ummon guruhi - Ohangim'.")


@dp.message(F.text == MENU_GALLERY)
async def menu_gallery(message: Message) -> None:
    user_mode[message.chat.id] = "gallery"
    await message.answer("🖼 Endi telefon/kompyuteringizdagi videoni shu yerga yuboring (fayl sifatida).")


@dp.message(F.text == MENU_IMAGE_COMPRESS)
async def menu_image_compress(message: Message) -> None:
    user_mode[message.chat.id] = "image_compress"
    await message.answer("🗜 Hajmini kichraytirmoqchi bo'lgan rasmni yuboring.")


@dp.message(F.text == MENU_VIDEO_COMPRESS)
async def menu_video_compress(message: Message) -> None:
    user_mode[message.chat.id] = "video_compress"
    await message.answer("🎞 Hajmini kichraytirmoqchi bo'lgan videoni yuboring.")


@dp.message(F.text == MENU_QR)
async def menu_qr(message: Message) -> None:
    user_mode[message.chat.id] = "qr"
    await message.answer("🔳 QR-kod yaratish uchun matn yoki linkni yuboring.")


@dp.message(F.text == MENU_TRIM)
async def menu_trim(message: Message) -> None:
    user_mode[message.chat.id] = "trim"
    await message.answer(
        "✂️ Kesish uchun avval videoni (fayl sifatida) yuboring. "
        "Keyin qaysi oralig'ini olishni so'rayman."
    )


@dp.message(F.text == MENU_INFO)
async def menu_info(message: Message) -> None:
    user_mode[message.chat.id] = "info"
    await message.answer(
        "ℹ️ Video linkini yuboring — men uni yuklamasdan turib "
        "sarlavhasi, muallifi va davomiyligini ko'rsataman."
    )


@dp.message(F.text == MENU_QR_SCAN)
async def menu_qr_scan(message: Message) -> None:
    user_mode[message.chat.id] = "qr_scan"
    await message.answer("🔎 QR-kod tasvirlangan rasmni (fayl sifatida) yuboring.")


@dp.message(F.text == MENU_RESIZE)
async def menu_resize(message: Message) -> None:
    user_mode[message.chat.id] = "resize"
    await message.answer("📐 O'lchamini moslamoqchi bo'lgan rasmni yuboring.")


@dp.message(F.text == MENU_STATS)
async def menu_stats(message: Message) -> None:
    await message.answer(stats.get_stats_text())


@dp.message(F.text == MENU_SETTINGS)
async def menu_settings(message: Message) -> None:
    hours = FOLLOWUP_DELAY_SECONDS // 3600
    await message.answer(
        "⚙️ Sozlamalar\n\n"
        f"• Watermark yashirish usuli: {WATERMARK_MODE}\n"
        f"• Watermark joylashuvi: {WATERMARK_POSITION}\n"
        f"• Rasm siqish sifati: {IMAGE_COMPRESS_QUALITY}/95\n"
        f"• Video siqish darajasi (CRF): {VIDEO_COMPRESS_CRF}\n"
        f"• Eslatma xabari: {hours} soatdan keyin\n"
        f"• Maksimal video davomiyligi: {MAX_VIDEO_DURATION_SECONDS // 60} daqiqa\n"
        f"• So'rovlar orasidagi minimal interval: {USER_COOLDOWN_SECONDS} soniya\n\n"
        "Bu qiymatlarni config.py faylidan o'zgartirishingiz mumkin."
    )


# ==================================================================
# 1-QADAM: LINK YOKI GALEREYA VIDEO KELGANDA — TANLOV SO'RASH
# ==================================================================

@dp.message(F.video)
async def handle_uploaded_video(message: Message) -> None:
    chat_id = message.chat.id
    wait = check_cooldown(chat_id)
    if wait > 0:
        await message.answer(f"⏱ Iltimos, {wait} soniya kuting va qayta urining.")
        return

    if message.video.duration and message.video.duration > MAX_VIDEO_DURATION_SECONDS:
        await message.answer(
            f"⚠️ Video juda uzun. Maksimal ruxsat etilgan: "
            f"{MAX_VIDEO_DURATION_SECONDS // 60} daqiqa."
        )
        return

    mode = user_mode.get(chat_id)

    # "🎞 Video siqish" tugmasi orqali kelgan bo'lsa — to'g'ridan-to'g'ri siqamiz
    if mode == "video_compress":
        await message.answer("✅ Video qabul qilindi! Siqilmoqda...")
        status_msg = await message.answer("⏳ Yuklab olinmoqda...")
        with tempfile.TemporaryDirectory() as tmp_dir:
            raw_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}.mp4")
            try:
                file_info = await bot.get_file(message.video.file_id)
                await bot.download_file(file_info.file_path, destination=raw_path)
            except Exception as e:
                await status_msg.edit_text(f"❌ Videoni yuklab bo'lmadi: {str(e)[:200]}")
                return
            await status_msg.edit_text("🎞 Video siqilmoqda...")
            compressed_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}_compressed.mp4")
            try:
                await asyncio.to_thread(compress_video, raw_path, compressed_path, VIDEO_COMPRESS_CRF)
            except Exception as e:
                logger.exception("[%s] Video siqishda xatolik", chat_id)
                await status_msg.edit_text(f"❌ Siqib bo'lmadi: {str(e)[:200]}")
                return
            original_mb = os.path.getsize(raw_path) / (1024 * 1024)
            compressed_mb = os.path.getsize(compressed_path) / (1024 * 1024)
            await status_msg.edit_text("📤 Yuborilmoqda...")
            try:
                await bot.send_video(
                    chat_id, FSInputFile(compressed_path),
                    caption=f"✅ Tayyor! {original_mb:.1f}MB → {compressed_mb:.1f}MB",
                )
            except TelegramAPIError:
                await status_msg.edit_text("❌ Video yuborilmadi.")
                return
            await status_msg.delete()
        stats.record_event("video_siqish", chat_id)
        return

    # "✂️ Video kesish" tugmasi orqali kelgan bo'lsa — videoni saqlab,
    # boshlanish/tugash vaqtini so'raymiz
    if mode == "trim":
        status_msg = await message.answer("⏳ Yuklab olinmoqda...")
        raw_path = os.path.join(TRIM_DIR, f"{chat_id}_{uuid.uuid4().hex}.mp4")
        try:
            file_info = await bot.get_file(message.video.file_id)
            await bot.download_file(file_info.file_path, destination=raw_path)
        except Exception as e:
            logger.exception("[%s] Kesish uchun video yuklashda xatolik", chat_id)
            await status_msg.edit_text(f"❌ Videoni yuklab bo'lmadi: {str(e)[:200]}")
            return

        try:
            duration = await asyncio.to_thread(get_video_duration, raw_path)
        except Exception:
            duration = None

        trim_pending[chat_id] = raw_path
        user_mode[chat_id] = "trim_times"
        dur_text = f" (davomiyligi: {int(duration)} soniya)" if duration else ""
        await status_msg.edit_text(
            f"✅ Video qabul qilindi{dur_text}.\n\n"
            "✂️ Qaysi oralig'ini olishni yozing.\n"
            "Format: <b>boshlanish-tugash</b> (soniyalarda)\n"
            "Masalan: <code>5-15</code> (5-soniyadan 15-soniyagacha)",
            parse_mode="HTML",
        )
        return

    # Aks holda — odatdagidek "Musiqa yoki Video (watermark)?" deb so'raymiz
    pending_choice[chat_id] = {"kind": "video", "file_id": message.video.file_id}
    await message.answer(
        "🎬 Video qabul qilindi! Nima kerak?",
        reply_markup=choice_keyboard(),
    )


# ==================================================================
# RASM (PHOTO) BILAN ISHLASH
# ==================================================================

@dp.message(F.photo)
async def handle_uploaded_photo(message: Message) -> None:
    chat_id = message.chat.id
    wait = check_cooldown(chat_id)
    if wait > 0:
        await message.answer(f"⏱ Iltimos, {wait} soniya kuting va qayta urining.")
        return

    mode = user_mode.get(chat_id)
    photo = message.photo[-1]  # eng katta hajmdagi versiyasi

    # 🔎 QR-kod o'qish rejimi — alohida, oddiy oqimdan tashqarida ishlaydi
    if mode == "qr_scan":
        status_msg = await message.answer("⏳ Rasm tekshirilmoqda...")
        with tempfile.TemporaryDirectory() as tmp_dir:
            raw_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}.jpg")
            try:
                file_info = await bot.get_file(photo.file_id)
                await bot.download_file(file_info.file_path, destination=raw_path)
            except Exception as e:
                logger.exception("[%s] QR uchun rasm yuklashda xatolik", chat_id)
                await status_msg.edit_text(f"❌ Rasmni yuklab bo'lmadi: {str(e)[:200]}")
                return
            try:
                results = await asyncio.to_thread(decode_qr_code, raw_path)
            except Exception as e:
                logger.exception("[%s] QR o'qishda xatolik", chat_id)
                await status_msg.edit_text(f"❌ QR-kodni o'qib bo'lmadi: {str(e)[:200]}")
                return
        if not results:
            await status_msg.edit_text("❌ Rasmda QR-kod topilmadi.")
            return
        text_out = "\n".join(f"🔎 {t}" for t in results)
        await status_msg.edit_text(f"✅ Topildi!\n\n{text_out}")
        stats.record_event("qr_scan", chat_id)
        schedule_followup(bot, chat_id)
        return

    # 📐 Rasm o'lchamini moslash rejimi — avval rasmni saqlaymiz, keyin
    # inline tugmalar orqali o'lcham shablonini so'raymiz
    if mode == "resize":
        status_msg = await message.answer("⏳ Yuklab olinmoqda...")
        raw_path = os.path.join(RESIZE_DIR, f"{chat_id}_{uuid.uuid4().hex}.jpg")
        try:
            file_info = await bot.get_file(photo.file_id)
            await bot.download_file(file_info.file_path, destination=raw_path)
        except Exception as e:
            logger.exception("[%s] Resize uchun rasm yuklashda xatolik", chat_id)
            await status_msg.edit_text(f"❌ Rasmni yuklab bo'lmadi: {str(e)[:200]}")
            return
        resize_pending[chat_id] = raw_path
        await status_msg.edit_text(
            "✅ Rasm qabul qilindi! Qaysi o'lchamga moslayman?",
            reply_markup=resize_preset_keyboard(),
        )
        return

    await message.answer("✅ Rasm qabul qilindi! Ishlov berilmoqda...")
    status_msg = await message.answer("⏳ Yuklab olinmoqda...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        raw_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}.jpg")
        try:
            file_info = await bot.get_file(photo.file_id)
            await bot.download_file(file_info.file_path, destination=raw_path)
        except Exception as e:
            logger.exception("[%s] Rasmni yuklab olishda xatolik", chat_id)
            await status_msg.edit_text(f"❌ Rasmni yuklab bo'lmadi: {str(e)[:200]}")
            return

        if mode == "image_compress":
            await status_msg.edit_text("🗜 Rasm siqilmoqda...")
            processed_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}_compressed.jpg")
            try:
                await asyncio.to_thread(compress_image, raw_path, processed_path, IMAGE_COMPRESS_QUALITY)
            except Exception as e:
                logger.exception("[%s] Rasm siqishda xatolik", chat_id)
                await status_msg.edit_text(f"❌ Siqib bo'lmadi: {str(e)[:200]}")
                return
            original_kb = os.path.getsize(raw_path) / 1024
            compressed_kb = os.path.getsize(processed_path) / 1024
            caption = f"✅ Tayyor! {original_kb:.0f}KB → {compressed_kb:.0f}KB"
            event = "rasm_siqish"
        else:
            await status_msg.edit_text("🖼 Watermark/belgi tozalanmoqda...")
            processed_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}_clean.jpg")
            try:
                await asyncio.to_thread(
                    remove_watermark_image, raw_path, processed_path,
                    WATERMARK_POSITION, WATERMARK_WIDTH_RATIO, WATERMARK_HEIGHT_RATIO,
                )
            except Exception:
                logger.exception("[%s] Rasm watermarkni tozalashda xatolik", chat_id)
                processed_path = raw_path
                await status_msg.edit_text("⚠️ Tozalab bo'lmadi, asl rasm yuborilmoqda...")
            caption = "✅ Tayyor!"
            event = "rasm"

        await status_msg.edit_text("📤 Yuborilmoqda...")
        try:
            await bot.send_photo(chat_id, FSInputFile(processed_path), caption=caption)
        except TelegramAPIError as e:
            logger.error("[%s] Rasm yuborishda xatolik: %s", chat_id, e)
            await status_msg.edit_text("❌ Rasm yuborilmadi.")
            return
        await status_msg.delete()

    stats.record_event(event, chat_id)
    schedule_followup(bot, chat_id)


# ==================================================================
# 2-QADAM: TANLOVGA JAVOB (Musiqa yoki Video) — CALLBACK
# ==================================================================

@dp.callback_query(F.data.startswith("choice:"))
async def handle_choice(callback: CallbackQuery) -> None:
    chat_id = callback.message.chat.id
    action = callback.data.split(":", 1)[1]  # "music" yoki "video"
    pending = pending_choice.pop(chat_id, None)
    await callback.answer()

    if not pending:
        await callback.message.edit_text(
            "⚠️ So'rov muddati tugagan. Iltimos, linkni yoki videoni qayta yuboring."
        )
        return

    label = "🎵 Musiqa" if action == "music" else "🖼 Video (watermark tozalangan)"
    await callback.message.edit_text(f"✅ Tanlandi: {label}. Ishlov berilmoqda...")
    status_msg = callback.message

    if pending["kind"] == "link":
        url = pending["url"]
        platform_name = pending.get("platform", "Video")
        if action == "video":
            await run_link_video(status_msg, chat_id, url, platform_name)
        else:
            await run_link_audio(status_msg, chat_id, url)
    else:  # kind == "video" (galereyadan)
        file_id = pending["file_id"]
        if action == "video":
            await run_gallery_video(status_msg, chat_id, file_id)
        else:
            await run_gallery_audio(status_msg, chat_id, file_id)


@dp.callback_query(F.data.startswith("resize:"))
async def handle_resize_choice(callback: CallbackQuery) -> None:
    chat_id = callback.message.chat.id
    preset_key = callback.data.split(":", 1)[1]
    await callback.answer()

    raw_path = resize_pending.pop(chat_id, None)
    if not raw_path or not os.path.exists(raw_path):
        await callback.message.edit_text("⚠️ Rasm topilmadi. Iltimos, qaytadan yuboring.")
        return

    target_size = IMAGE_RESIZE_PRESETS.get(preset_key)
    if not target_size:
        await callback.message.edit_text("❌ Noto'g'ri o'lcham tanlandi.")
        return

    await callback.message.edit_text("📐 Rasm moslanmoqda...")
    output_path = os.path.join(RESIZE_DIR, f"{chat_id}_{uuid.uuid4().hex}_resized.jpg")
    try:
        await asyncio.to_thread(resize_image_to_size, raw_path, output_path, target_size)
        await bot.send_photo(
            chat_id, FSInputFile(output_path),
            caption=f"✅ Tayyor! {target_size[0]}x{target_size[1]} o'lchamiga moslandi.",
        )
        await callback.message.delete()
        stats.record_event("resize", chat_id)
        schedule_followup(bot, chat_id)
    except Exception as e:
        logger.exception("[%s] Rasm o'lchamini moslashda xatolik", chat_id)
        await callback.message.edit_text(f"❌ Xatolik: {str(e)[:200]}")
    finally:
        for p in (raw_path, output_path):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


# ==================================================================
# 3-QADAM: HAQIQIY ISHLOV BERISH FUNKSIYALARI
# ==================================================================

async def run_link_video(status_msg: Message, chat_id: int, url: str, platform_name: str) -> None:
    logger.info("[%s] %s (video) -> %s", chat_id, platform_name, url)
    await status_msg.edit_text("⏳ Video yuklanmoqda...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            raw_path = await asyncio.to_thread(download_video, url, tmp_dir)
        except ValueError as e:
            await status_msg.edit_text(f"⚠️ {e}")
            return
        except Exception as e:
            # Video sifatida yuklab bo'lmadi — balki bu shunchaki rasm postidir,
            # shuni sinab ko'ramiz (masalan Instagram rasm posti).
            logger.info("[%s] Video sifatida yuklanmadi, rasm sifatida urinib ko'ramiz: %s", chat_id, e)
            await status_msg.edit_text("🖼 Bu video emas, rasm bo'lishi mumkin — tekshirilmoqda...")
            try:
                image_raw_path = await asyncio.to_thread(download_image_from_url, url, tmp_dir)
            except Exception:
                logger.exception("[%s] Yuklab olishda xatolik", chat_id)
                await status_msg.edit_text(
                    "❌ Yuklab bo'lmadi.\n"
                    "Sabablari: kontent maxfiy akkauntdan, link noto'g'ri, "
                    "yoki tarmoqda vaqtinchalik muammo bo'lishi mumkin.\n"
                    f"Texnik tafsilot: {str(e)[:200]}"
                )
                return

            await status_msg.edit_text("🖼 Rasm watermarki tozalanmoqda...")
            processed_image_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}_clean.jpg")
            try:
                await asyncio.to_thread(
                    remove_watermark_image, image_raw_path, processed_image_path,
                    WATERMARK_POSITION, WATERMARK_WIDTH_RATIO, WATERMARK_HEIGHT_RATIO,
                )
            except Exception:
                logger.exception("[%s] Rasm watermarkni tozalashda xatolik", chat_id)
                processed_image_path = image_raw_path
                await status_msg.edit_text("⚠️ Tozalab bo'lmadi, asl rasm yuborilmoqda...")

            await status_msg.edit_text("📤 Rasm yuborilmoqda...")
            try:
                await bot.send_photo(chat_id, FSInputFile(processed_image_path), caption=f"✅ Tayyor! ({platform_name})")
            except TelegramAPIError:
                await status_msg.edit_text("❌ Rasm yuborilmadi.")
                return
            await status_msg.delete()
            stats.record_event("rasm", chat_id)
            schedule_followup(bot, chat_id)
            return

        await status_msg.edit_text("🎬 Username/watermark tozalanmoqda...")
        processed_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}_clean.mp4")
        try:
            await asyncio.to_thread(
                remove_watermark, raw_path, processed_path, WATERMARK_POSITION, WATERMARK_MODE
            )
        except Exception:
            logger.exception("[%s] Watermarkni tozalashda xatolik", chat_id)
            processed_path = raw_path
            await status_msg.edit_text("⚠️ Watermarkni tozalab bo'lmadi, asl video yuborilmoqda...")

        await status_msg.edit_text("📤 Video yuborilmoqda...")
        try:
            await bot.send_video(chat_id, FSInputFile(processed_path), caption=f"✅ Tayyor! ({platform_name})")
        except TelegramAPIError as e:
            logger.error("[%s] Video yuborishda xatolik: %s", chat_id, e)
            await status_msg.edit_text(
                "❌ Video juda katta yoki Telegram uni qabul qilmadi. "
                "(Telegram bot orqali maksimal 50 MB gacha fayl yuborish mumkin.)"
            )
            return
        await status_msg.delete()

    logger.info("[%s] %s video muvaffaqiyatli yuborildi", chat_id, platform_name)
    stats.record_event("video", chat_id)
    schedule_followup(bot, chat_id)


async def run_link_audio(status_msg: Message, chat_id: int, url: str) -> None:
    logger.info("[%s] Link (audio) -> %s", chat_id, url)
    await status_msg.edit_text("⏳ Audio (musiqa) yuklanmoqda...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            title, filepath = await asyncio.to_thread(download_audio_from_url, url, tmp_dir)
        except Exception as e:
            logger.exception("[%s] Audio yuklashda xatolik", chat_id)
            await status_msg.edit_text(
                f"❌ Audio yuklab bo'lmadi.\nTexnik tafsilot: {str(e)[:200]}"
            )
            return

        await status_msg.edit_text("📤 Yuborilmoqda...")
        try:
            await bot.send_audio(chat_id, FSInputFile(filepath), title=title, caption=f"🎵 {title}")
        except TelegramAPIError as e:
            logger.error("[%s] Audio yuborishda xatolik: %s", chat_id, e)
            await status_msg.edit_text("❌ Audio faylni yuborib bo'lmadi.")
            return
        await status_msg.delete()

    logger.info("[%s] Link'dan audio muvaffaqiyatli yuborildi", chat_id)
    stats.record_event("musiqa", chat_id)
    schedule_followup(bot, chat_id)


async def run_gallery_video(status_msg: Message, chat_id: int, file_id: str) -> None:
    logger.info("[%s] Galereya video (watermark)", chat_id)
    await status_msg.edit_text("⏳ Video yuklab olinmoqda...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        raw_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}.mp4")
        try:
            file_info = await bot.get_file(file_id)
            await bot.download_file(file_info.file_path, destination=raw_path)
        except Exception as e:
            logger.exception("[%s] Videoni yuklab olishda xatolik", chat_id)
            await status_msg.edit_text(f"❌ Videoni yuklab bo'lmadi: {str(e)[:200]}")
            return

        await status_msg.edit_text("🎬 Watermark/belgi tozalanmoqda...")
        processed_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}_clean.mp4")
        try:
            await asyncio.to_thread(
                remove_watermark, raw_path, processed_path, WATERMARK_POSITION, WATERMARK_MODE
            )
        except Exception:
            logger.exception("[%s] Watermarkni tozalashda xatolik", chat_id)
            processed_path = raw_path
            await status_msg.edit_text("⚠️ Tozalab bo'lmadi, asl video yuborilmoqda...")

        await status_msg.edit_text("📤 Video yuborilmoqda...")
        try:
            await bot.send_video(chat_id, FSInputFile(processed_path), caption="✅ Tayyor!")
        except TelegramAPIError as e:
            logger.error("[%s] Video yuborishda xatolik: %s", chat_id, e)
            await status_msg.edit_text("❌ Video juda katta yoki yuborilmadi.")
            return
        await status_msg.delete()

    logger.info("[%s] Galereya videosi muvaffaqiyatli yuborildi", chat_id)
    stats.record_event("video", chat_id)
    schedule_followup(bot, chat_id)


async def run_gallery_audio(status_msg: Message, chat_id: int, file_id: str) -> None:
    logger.info("[%s] Galereya video (audio ajratish)", chat_id)
    await status_msg.edit_text("⏳ Video yuklab olinmoqda...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        raw_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}.mp4")
        try:
            file_info = await bot.get_file(file_id)
            await bot.download_file(file_info.file_path, destination=raw_path)
        except Exception as e:
            logger.exception("[%s] Videoni yuklab olishda xatolik", chat_id)
            await status_msg.edit_text(f"❌ Videoni yuklab bo'lmadi: {str(e)[:200]}")
            return

        await status_msg.edit_text("🎵 Audio ajratilmoqda...")
        audio_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}.mp3")
        try:
            await asyncio.to_thread(extract_audio_from_local_video, raw_path, audio_path)
        except Exception as e:
            logger.exception("[%s] Audio ajratishda xatolik", chat_id)
            await status_msg.edit_text(f"❌ Audio ajratib bo'lmadi: {str(e)[:200]}")
            return

        await status_msg.edit_text("📤 Yuborilmoqda...")
        try:
            await bot.send_audio(chat_id, FSInputFile(audio_path), caption="🎵 Tayyor!")
        except TelegramAPIError as e:
            logger.error("[%s] Audio yuborishda xatolik: %s", chat_id, e)
            await status_msg.edit_text("❌ Audio faylni yuborib bo'lmadi.")
            return
        await status_msg.delete()

    logger.info("[%s] Galereya audiosi muvaffaqiyatli yuborildi", chat_id)
    stats.record_event("musiqa", chat_id)
    schedule_followup(bot, chat_id)


# ==================================================================
# MUSIQA QIDIRISH
# ==================================================================

async def process_music_query(message: Message, query: str) -> None:
    chat_id = message.chat.id
    wait = check_cooldown(chat_id)
    if wait > 0:
        await message.answer(f"⏱ Iltimos, {wait} soniya kuting va qayta urining.")
        return

    logger.info("[%s] Musiqa qidiruvi: %s", chat_id, query)
    await message.answer("✅ So'rov qabul qilindi! Qidirilmoqda...")
    status_msg = await message.answer("🔎 Qidirilmoqda...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            title, filepath = await asyncio.to_thread(search_and_download_music, query, tmp_dir)
        except Exception as e:
            logger.exception("[%s] Musiqa qidirishda xatolik", chat_id)
            await status_msg.edit_text(
                f"❌ Topilmadi yoki yuklab bo'lmadi.\nTexnik tafsilot: {str(e)[:200]}"
            )
            return

        await status_msg.edit_text("📤 Yuborilmoqda...")
        try:
            await message.answer_audio(FSInputFile(filepath), title=title, caption=f"🎵 {title}")
        except TelegramAPIError as e:
            logger.error("[%s] Audio yuborishda xatolik: %s", chat_id, e)
            await status_msg.edit_text("❌ Audio faylni yuborib bo'lmadi.")
            return
        await status_msg.delete()

    logger.info("[%s] Musiqa muvaffaqiyatli yuborildi: %s", chat_id, title)
    stats.record_event("musiqa", chat_id)
    schedule_followup(bot, chat_id)


# ==================================================================
# MATNLI XABARLARNI YO'NALTIRISH
# ==================================================================

@dp.message(F.text)
async def handle_text(message: Message) -> None:
    text = message.text or ""
    chat_id = message.chat.id
    mode = user_mode.get(chat_id)

    # QR-kod rejimida bo'lsa — matn ichida link bo'lsa ham, baribir QR yaratamiz
    if mode == "qr":
        wait = check_cooldown(chat_id)
        if wait > 0:
            await message.answer(f"⏱ Iltimos, {wait} soniya kuting va qayta urining.")
            return
        await message.answer("🔳 QR-kod yaratilmoqda...")
        with tempfile.TemporaryDirectory() as tmp_dir:
            qr_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}.png")
            try:
                await asyncio.to_thread(generate_qr_code, text, qr_path)
            except Exception as e:
                logger.exception("[%s] QR-kod yaratishda xatolik", chat_id)
                await message.answer(f"❌ QR-kod yaratib bo'lmadi: {str(e)[:200]}")
                return
            await message.answer_photo(FSInputFile(qr_path), caption="✅ QR-kod tayyor!")
        stats.record_event("qr", chat_id)
        schedule_followup(bot, chat_id)
        return

    # ✂️ Video kesish: foydalanuvchi "boshlanish-tugash" formatida vaqt yozadi
    if mode == "trim_times":
        raw_path = trim_pending.get(chat_id)
        if not raw_path or not os.path.exists(raw_path):
            user_mode[chat_id] = None
            await message.answer(
                "⚠️ Video topilmadi. Iltimos, /cancel bosib, qaytadan urinib ko'ring."
            )
            return

        parts = text.replace(" ", "").split("-")
        if len(parts) != 2:
            await message.answer(
                "❗ Noto'g'ri format. Masalan: <code>5-15</code> deb yozing.",
                parse_mode="HTML",
            )
            return
        try:
            start_s, end_s = float(parts[0]), float(parts[1])
            if start_s < 0 or end_s <= start_s:
                raise ValueError
        except ValueError:
            await message.answer(
                "❗ Vaqtlar noto'g'ri. Tugash vaqti boshlanishdan katta bo'lishi kerak. "
                "Masalan: <code>5-15</code>",
                parse_mode="HTML",
            )
            return

        wait = check_cooldown(chat_id)
        if wait > 0:
            await message.answer(f"⏱ Iltimos, {wait} soniya kuting va qayta urining.")
            return

        status_msg = await message.answer("✂️ Video kesilmoqda...")
        output_path = os.path.join(TRIM_DIR, f"{chat_id}_{uuid.uuid4().hex}_trimmed.mp4")
        try:
            await asyncio.to_thread(trim_video, raw_path, output_path, start_s, end_s)
            await status_msg.edit_text("📤 Yuborilmoqda...")
            await bot.send_video(
                chat_id, FSInputFile(output_path),
                caption=f"✅ Tayyor! ({start_s:.0f}s - {end_s:.0f}s)",
            )
            await status_msg.delete()
            stats.record_event("video_kesish", chat_id)
            schedule_followup(bot, chat_id)
        except Exception as e:
            logger.exception("[%s] Video kesishda xatolik", chat_id)
            await status_msg.edit_text(f"❌ Kesib bo'lmadi: {str(e)[:200]}")
        finally:
            trim_pending.pop(chat_id, None)
            user_mode[chat_id] = None
            for p in (raw_path, output_path):
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
        return

    # ℹ️ Video ma'lumoti: linkni yuklamasdan turib ma'lumot beramiz
    if mode == "info":
        url = extract_url(text, GENERIC_URL_RE)
        if not url:
            await message.answer("❗ Iltimos, video linkini yuboring (masalan Instagram yoki TikTok linki).")
            return
        wait = check_cooldown(chat_id)
        if wait > 0:
            await message.answer(f"⏱ Iltimos, {wait} soniya kuting va qayta urining.")
            return
        status_msg = await message.answer("🔎 Ma'lumot olinmoqda...")
        try:
            info = await asyncio.to_thread(get_media_info, url)
            await status_msg.edit_text(format_info_message(info), parse_mode="HTML")
            stats.record_event("info", chat_id)
        except Exception as e:
            logger.exception("[%s] Ma'lumot olishda xatolik", chat_id)
            await status_msg.edit_text(f"❌ Ma'lumot olib bo'lmadi: {str(e)[:200]}")
        return

    url = extract_url(text, GENERIC_URL_RE)

    if url:
        wait = check_cooldown(chat_id)
        if wait > 0:
            await message.answer(f"⏱ Iltimos, {wait} soniya kuting va qayta urining.")
            return
        platform_name = detect_platform_name(url)
        pending_choice[chat_id] = {"kind": "link", "url": url, "platform": platform_name}
        await message.answer(
            f"🔗 {platform_name} link qabul qilindi! Nima kerak?",
            reply_markup=choice_keyboard(),
        )
        return

    if mode == "music":
        await process_music_query(message, text)
        return

    if mode == "gallery":
        await message.answer("🖼 Iltimos, videoni matn emas, fayl sifatida yuboring.")
        return

    if mode == "trim":
        await message.answer("✂️ Iltimos, avval videoni (fayl sifatida) yuboring.")
        return

    if mode == "qr_scan":
        await message.answer("🔎 Iltimos, QR-kod tasvirlangan rasmni yuboring.")
        return

    if mode == "resize":
        await message.answer("📐 Iltimos, o'lchamini moslamoqchi bo'lgan rasmni yuboring.")
        return

    await message.answer(
        "Tushunmadim 🙂 Pastdagi menyudan bo'lim tanlang yoki to'g'ridan-to'g'ri "
        "video linkini (Instagram, TikTok, YouTube va h.k.) yuboring. "
        "Yordam uchun /help yozing.",
        reply_markup=main_menu_keyboard(),
    )


# ==================================================================
# XATOLIKLARNI GLOBAL USHLASH
# ==================================================================

@dp.error()
async def global_error_handler(event: ErrorEvent) -> bool:
    # DIQQAT: bu yerda faol "except" bloki ichida emasmiz, shuning uchun
    # logger.exception() o'rniga exc_info orqali xatolikni to'g'ri
    # logga yozamiz (aks holda traceback noto'g'ri/bo'sh chiqadi).
    logger.error(
        "Kutilmagan xatolik: %s", event.exception, exc_info=event.exception
    )
    return True


# ==================================================================
# ISHGA TUSHIRISH
# ==================================================================

async def main() -> None:
    logger.info("Bot ishga tushmoqda...")

    # 📢 Barcha foydalanuvchilarga avtomatik soatlik xabar yuborish
    # tizimini fon vazifasi (background task) sifatida ishga tushiramiz.
    broadcast_task = asyncio.create_task(admin.hourly_broadcast_loop(bot))

    try:
        await dp.start_polling(bot)
    finally:
        broadcast_task.cancel()
        logger.info("Bot to'xtatildi.")
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot foydalanuvchi tomonidan to'xtatildi (Ctrl+C).")
