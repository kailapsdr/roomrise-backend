import os
from dotenv import load_dotenv

load_dotenv()

CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")

try:
    import cloudinary
    import cloudinary.uploader
    if CLOUD_NAME:
        cloudinary.config(
            cloud_name=CLOUD_NAME,
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        )
        USE_CLOUDINARY = True
        print("[STORAGE] Cloudinary aktif")
    else:
        USE_CLOUDINARY = False
        print("[STORAGE] Cloudinary tidak diset — pakai lokal")
except ImportError:
    USE_CLOUDINARY = False
    print("[STORAGE] Cloudinary tidak tersedia — pakai lokal")


def upload_image(file_bytes: bytes, filename: str) -> str:
    """Upload gambar, return URL. Pakai Cloudinary kalau ada, lokal kalau tidak."""
    if USE_CLOUDINARY:
        import cloudinary.uploader
        result = cloudinary.uploader.upload(
            file_bytes,
            public_id=filename,
            folder="roomrise",
            overwrite=True,
        )
        return result["secure_url"]
    else:
        from pathlib import Path
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)
        filepath = upload_dir / filename
        with open(filepath, "wb") as f:
            f.write(file_bytes)
        return f"/uploads/{filename}"


def delete_image(url: str):
    """Hapus gambar lama."""
    if USE_CLOUDINARY and url and "cloudinary" in url:
        try:
            import cloudinary.uploader
            public_id = "roomrise/" + url.split("/roomrise/")[-1].split(".")[0]
            cloudinary.uploader.destroy(public_id)
        except Exception:
            pass
    else:
        from pathlib import Path
        if url and url.startswith("/uploads/"):
            path = Path(url.lstrip("/"))
            if path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass