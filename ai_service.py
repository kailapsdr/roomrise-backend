import os
import random
import json
from dotenv import load_dotenv

load_dotenv()

# === YOLOv8 Setup ===
try:
    from ultralytics import YOLO
    model = YOLO("yolov8n.pt")
    USE_YOLO = True
    print("[AI] YOLOv8 aktif")
except ImportError:
    USE_YOLO = False
    print("[AI] YOLOv8 tidak tersedia — pakai simulasi")

# === Gemini Setup ===
try:
    import google.generativeai as genai
    GEMINI_KEY = os.getenv("GEMINI_API_KEY")
    if GEMINI_KEY:
        genai.configure(api_key=GEMINI_KEY)
        gemini_model = genai.GenerativeModel("gemini-2.0-flash")
        USE_LLM = True
        print("[AI] Gemini aktif")
    else:
        USE_LLM = False
        print("[AI] Gemini API key tidak ditemukan — pakai simulasi")
except ImportError:
    USE_LLM = False
    print("[AI] Gemini tidak tersedia — pakai simulasi")


FALLBACK_STEPS = [
    "Ambil satu pakaian kotor di lantai dan masukkan ke keranjang cucian",
    "Kumpulkan semua sampah kecil (bungkus snack, tisu) dan buang ke tempat sampah",
    "Rapikan buku atau kertas yang berserakan di meja, tumpuk dengan rapi",
    "Lipat satu selimut atau sprei yang berantakan di kasur",
    "Simpan charger atau kabel yang berserakan ke satu tempat",
    "Cuci satu piring atau gelas kotor yang ada di meja",
    "Sapu area kecil di sekitar meja belajar",
    "Taruh sepatu atau sandal yang berantakan ke rak",
    "Buang botol minum kosong ke tempat sampah",
    "Rapikan isi tas — keluarkan yang tidak perlu",
]


def analyze_room_image(image_path: str) -> dict:
    if USE_YOLO:
        results = model(image_path, verbose=False)
        detections = results[0].boxes
        total_objects = len(detections)
        hoarding_index = min(10, max(1, total_objects // 2))
        target_items = min(7, max(3, total_objects))
        return {"hoarding_index": hoarding_index, "target_items": target_items}
    else:
        return {
            "hoarding_index": random.randint(3, 10),
            "target_items": random.randint(3, 7),
        }


def generate_atomic_steps(target_items: int) -> list[str]:
    if USE_LLM:
        try:
            prompt = f"""Kamu adalah asisten yang membantu orang dengan executive dysfunction untuk merapikan kamar.
Buatkan tepat {target_items} langkah SANGAT SEDERHANA dan SPESIFIK untuk merapikan kamar.

Aturan:
- Setiap langkah harus bisa dikerjakan dalam 1-2 menit
- Gunakan bahasa Indonesia yang ramah dan tidak menghakimi
- Setiap langkah dimulai dengan kata kerja aksi (Ambil, Lipat, Taruh, dll)
- Jangan gunakan kata "semua" — fokus pada SATU barang per langkah

Balas HANYA dalam format JSON array of strings, tanpa penjelasan lain.
Contoh: ["Ambil satu baju kotor di lantai dan taruh ke keranjang", "Buang satu bungkus snack ke tempat sampah"]"""

            response = gemini_model.generate_content(prompt)
            text = response.text.strip()
            # Bersihkan kalau ada markdown backtick
            text = text.replace("```json", "").replace("```", "").strip()
            steps = json.loads(text)
            if isinstance(steps, list) and len(steps) >= target_items:
                return steps[:target_items]
        except Exception as e:
            print(f"[AI] Gemini error, fallback ke simulasi: {e}")

    random.shuffle(FALLBACK_STEPS)
    return FALLBACK_STEPS[:target_items]


def compare_before_after(before_path: str, after_path: str) -> dict:
    if USE_YOLO:
        if before_path.startswith("/"):
            before_path = before_path.lstrip("/")
        if after_path.startswith("/"):
            after_path = after_path.lstrip("/")

        results_before = model(before_path, verbose=False)
        results_after = model(after_path, verbose=False)
        objects_before = len(results_before[0].boxes)
        objects_after = len(results_after[0].boxes)

        if objects_before == 0:
            improvement = 50
        else:
            improvement = max(0, int((objects_before - objects_after) / objects_before * 100))

        is_valid = improvement >= 10
        return {"improvement_percent": improvement, "is_valid": is_valid}
    else:
        improvement = random.randint(40, 95)
        is_valid = improvement >= 30
        return {"improvement_percent": improvement, "is_valid": is_valid}