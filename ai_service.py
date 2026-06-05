import random


def analyze_room_image(image_path: str) -> dict:
    """Simulasi YOLOv8: analisis foto ruangan."""
    hoarding_index = random.randint(3, 10)
    target_items = random.randint(3, 7)
    return {"hoarding_index": hoarding_index, "target_items": target_items}


def generate_atomic_steps(target_items: int) -> list[str]:
    """Simulasi LLM: pecah tugas jadi langkah kecil."""
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
    """Simulasi validasi before/after — anti-gaming."""
    improvement = random.randint(40, 95)
    is_valid = improvement >= 30
    return {"improvement_percent": improvement, "is_valid": is_valid}