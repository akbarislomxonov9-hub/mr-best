# O'zgarishlar tarixi

## 🐞 Tuzatilgan xatoliklar

1. **`bot.py` — `@dp.errors()` ishlamas edi.** aiogram 3'da bunday
   dekorator mavjud emas (u aiogram 2'ga tegishli edi) — bot import
   vaqtidayoq `AttributeError` bilan qulab tushishi mumkin edi.
   To'g'ri shakl: `@dp.error()` + `event: ErrorEvent`.
2. **Xatolik logi noto'g'ri yozilardi.** `logger.exception(...)` faol
   `except` bloki tashqarisida chaqirilgani uchun traceback o'rniga
   bo'sh/noto'g'ri ma'lumot yozilardi. `logger.error(..., exc_info=...)`
   ga almashtirildi.
3. **`watermark.py` — `subprocess.run(["cp", ...])` Windows'da
   ishlamaydi** (`cp` — faqat Linux/Mac buyrug'i). `shutil.copyfile()`
   bilan almashtirildi — endi barcha platformalarda ishlaydi.
4. **Video yuklashda ikki marta tarmoqqa so'rov yuborilardi**
   (`extract_info` ikki marta chaqirilgan). Endi bitta so'rov bilan
   ham davomiylik tekshiriladi, ham yuklanadi — tezroq ishlaydi.
5. **`info.py`dagi HTML xavfsizligi.** Video sarlavhasi/muallif nomida
   `<`, `>`, `&` kabi belgilar bo'lsa, Telegram HTML parse_mode xabarni
   butunlay rad etib, xatolik berishi mumkin edi. Endi `html.escape()`
   bilan xavfsizlantirilgan.
6. **`.env`dagi tokenni Windows terminalida ishlatishda muammo**
   bo'lmasligi uchun fayl nomini albatta **`.env`** deb qoldiring
   (nuqta bilan boshlanishi shart — ba'zi tizimlar yuklab olishda
   nuqtani "_" ga almashtirib qo'yishi mumkin, shuni tekshiring).

## ✨ Qo'shilgan 5 ta yangi funksional bo'lim

1. **✂️ Video kesish (trim)** — `watermark.py`dagi `trim_video()` va
   `get_video_duration()`. Video yuboriladi → bot davomiyligini
   ko'rsatadi → foydalanuvchi `5-15` kabi oraliq yozadi → bot faqat
   shu qismini kesib yuboradi.
2. **ℹ️ Video ma'lumoti** — yangi `info.py` moduli. Linkni
   **yuklamasdan** turib (`download=False`) sarlavha, muallif,
   davomiylik, ko'rishlar va layklar sonini ko'rsatadi.
3. **🔎 QR-kod o'qish** — `qr_tools.py`ga qo'shilgan
   `decode_qr_code()` (OpenCV asosida). Foydalanuvchi QR-kodli rasm
   yuboradi, bot ichidagi matn/linkni o'qib beradi.
4. **📐 Rasm o'lchamini moslash** — `image_tools.py`ga qo'shilgan
   `resize_image_to_size()`. Instagram Story (1080x1920), Post
   (1080x1350), Kvadrat (1080x1080), Thumbnail (1280x720) tayyor
   shablonlari orqali rasmni "cover" usulida (nisbatni buzmasdan)
   kerakli o'lchamga moslaydi.
5. **📢 Admin panel + avtomatik soatlik xabar** — yangi `admin.py`
   moduli:
   - `/broadcast Xabar matni` — faqat `.env`dagi `ADMIN_IDS`da
     ko'rsatilgan foydalanuvchilar barcha botdan foydalanganlarga
     xabar yubora oladi.
   - Fon vazifasi (`hourly_broadcast_loop`) — har soatda barcha ma'lum
     foydalanuvchilarga tasodifiy foydali maslahat xabarini avtomatik
     yuboradi (`config.py`dagi `HOURLY_BROADCAST_MESSAGES` ro'yxatidan).
   - `stats.py`ga foydalanuvchilar ro'yxatini **diskka saqlash**
     (`known_users.json`) qo'shildi — bot qayta ishga tushirilsa ham
     kimlarga xabar yuborish kerakligini "unutmaydi".

## 📋 Yangilangan asosiy menyu

```
📥 Instagram        🎬 TikTok
🎵 Musiqa            🖼 Galereya video
🗜 Rasm siqish       🎞 Video siqish
✂️ Video kesish      ℹ️ Video ma'lumoti
🔳 QR-kod yaratish   🔎 QR o'qish
📐 Rasm o'lchami     📊 Statistika
⚙️ Sozlamalar
```
