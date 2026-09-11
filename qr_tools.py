"""
qr_tools.py — matn/linkdan QR-kod yaratish va rasmdagi QR-kodni o'qish
(skanerlash).
"""

import qrcode
import cv2


def generate_qr_code(text: str, output_path: str) -> None:
    """Berilgan matn/link uchun QR-kod rasmini yaratib, faylga saqlaydi."""
    img = qrcode.make(text)
    img.save(output_path)


def decode_qr_code(image_path: str) -> list[str]:
    """
    Berilgan rasm faylidagi barcha QR-kodlarni o'qib, ularning matn/link
    qiymatlarini ro'yxat qilib qaytaradi. Hech narsa topilmasa — bo'sh
    ro'yxat qaytaradi (xatolik chiqarmaydi).
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("Rasmni ochib bo'lmadi — fayl buzilgan bo'lishi mumkin.")

    detector = cv2.QRCodeDetector()

    # Avval bir nechta QR-kodni bir vaqtda aniqlashga urinamiz
    try:
        ok, decoded_texts, _points, _ = detector.detectAndDecodeMulti(img)
        if ok:
            results = [t for t in decoded_texts if t]
            if results:
                return results
    except Exception:
        pass

    # Agar multi-detect ishlamasa, bitta QR-kod uchun urinib ko'ramiz
    text, _points, _ = detector.detectAndDecode(img)
    return [text] if text else []
