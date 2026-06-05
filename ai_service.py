import random

# Coba import YOLOv8 — kalau gagal, pakai simulasi
try:
    from ultralytics import YOLO
    model = YOLO("yolov8n.pt")  # model kecil, otomatis download pertama kali
    USE_YOLO = True
    print("[AI] YOLOv8 aktif — pakai deteksi beneran")
except ImportError:
    USE_YOLO = False
    print("[AI] YOLOv8 tidak tersedia — pakai simulasi")


def analyze_room_image(image_path: str) -> dict:
    """Analisis foto ruangan: hitung barang berantakan."""
    if USE_YOLO:
        results = model(image_path, verbose=False)
        detections = results[0].boxes
        total_objects = len(detections)

        # Hoarding index: semakin banyak barang, semakin tinggi
        hoarding_index = min(10, max(1, total_objects // 2))

        # Target items: berapa barang yang harus dirapikan (maks 7)
        target_items = min(7, max(3, total_objects))

        return {"hoarding_index": hoarding_index, "target_items": target_items}
    else:
        hoarding_index = random.randint(3, 10)
        target_items = random.randint(3, 7)
        return {"hoarding_index": hoarding_index, "target_items": target_items}


def generate_atomic_steps(target_items: int) -> list[str]:
    """Pecah tugas jadi langkah kecil berdasarkan jumlah target."""
    all_steps = [
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
    random.shuffle(all_steps)
    return all_steps[:target_items]


def compare_before_after(before_path: str, after_path: str) -> dict:
    """Bandingkan foto before/after — anti-gaming."""
    if USE_YOLO:
        # Pastikan path menunjuk ke file di disk, bukan URL
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