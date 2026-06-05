from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from database import engine, Base, SessionLocal
from auth import hash_password, verify_password, create_access_token
import models
import string
import schemas
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from auth import hash_password, verify_password, create_access_token, decode_access_token
import uuid
from pathlib import Path
from fastapi import UploadFile, File
from fastapi.staticfiles import StaticFiles
from ai_service import analyze_room_image, generate_atomic_steps, compare_before_after
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from cron import reset_expired_streaks
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests


Base.metadata.create_all(bind=engine)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_AVATAR_SIZE = 5 * 1024 * 1024  # 5 MB

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
scheduler = BackgroundScheduler()
scheduler.add_job(reset_expired_streaks, "cron", hour=0, minute=0)
scheduler.start()
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# Dependency: kasih database session ke endpoint, dan tutup setelahnya
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> models.User:
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token tidak valid atau kadaluarsa",
        )
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User tidak ditemukan",
        )
    return user        


@app.get("/")
def home():
    return {"message": "RoomRise backend jalan!"}


@app.get("/db-test")
def db_test():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        return {"db": "terhubung!", "hasil": result.scalar()}


@app.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: schemas.UserRegister, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email sudah digunakan")

    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username sudah digunakan")

    new_user = models.User(
        email=user.email,
        username=user.username,
        password_hash=hash_password(user.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Bikin streak dan wallet default untuk user baru
    db.add(models.Streak(user_id=new_user.id))
    db.add(models.Wallet(user_id=new_user.id))
    db.commit()

    return new_user

@app.post("/login", response_model=schemas.TokenResponse)
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.username == credentials.username
    ).first()

    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Username atau password salah",
        )

    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer"}

@app.get("/me", response_model=schemas.UserResponse)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user

@app.post("/logout")
def logout(current_user: models.User = Depends(get_current_user)):
    return {"message": "Logout berhasil"}

import random
from datetime import datetime, timedelta, timezone


@app.post("/forgot-password")
def forgot_password(req: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == req.email).first()

    # Balasan selalu sama, baik email terdaftar maupun tidak — biar tidak bisa dipakai
    # untuk menebak email mana yang punya akun (best practice keamanan)
    generic_response = {"message": "Jika email terdaftar, instruksi telah dikirim"}

    if not user:
        return generic_response

    # Hapus OTP lama yang belum kepakai untuk user ini
    db.query(models.PasswordReset).filter(
        models.PasswordReset.user_id == user.id
    ).delete()

    # Bikin OTP 6 digit
    otp = f"{random.randint(0, 999999):06d}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    reset = models.PasswordReset(user_id=user.id, otp=otp, expires_at=expires_at)
    db.add(reset)
    db.commit()

    # PENGEMBANGAN: cetak ke terminal. Nanti ganti dengan kirim email beneran.
    print("=" * 60)
    print(f"  PASSWORD RESET OTP untuk {user.email}")
    print(f"  OTP: {otp}")
    print(f"  Kadaluarsa: {expires_at.isoformat()}")
    print("=" * 60)

    return generic_response


@app.post("/reset-password")
def reset_password(req: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == req.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Permintaan tidak valid")

    reset = (
        db.query(models.PasswordReset)
        .filter(
            models.PasswordReset.user_id == user.id,
            models.PasswordReset.otp == req.otp,
        )
        .first()
    )

    if not reset:
        raise HTTPException(status_code=400, detail="OTP tidak valid")

    if reset.expires_at < datetime.now(timezone.utc):
        # Bersihkan OTP yang sudah kadaluarsa
        db.delete(reset)
        db.commit()
        raise HTTPException(status_code=400, detail="OTP sudah kadaluarsa")

    # Ganti password
    user.password_hash = hash_password(req.new_password)
    db.delete(reset)  # OTP sekali pakai
    db.commit()

    return {"message": "Password berhasil diganti"}

@app.patch("/profile/username", response_model=schemas.UserResponse)
def update_username(
    req: schemas.UsernameUpdateRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Username sama dengan sekarang? langsung kembalikan
    if req.username == current_user.username:
        return current_user

    # Cek apakah username sudah dipakai user lain
    existing = db.query(models.User).filter(
        models.User.username == req.username,
        models.User.id != current_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username sudah digunakan")

    current_user.username = req.username
    db.commit()
    db.refresh(current_user)
    return current_user

@app.patch("/profile/avatar", response_model=schemas.UserResponse)
async def update_avatar(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Format file harus JPG, PNG, atau WEBP",
        )

    contents = await file.read()
    if len(contents) > MAX_AVATAR_SIZE:
        raise HTTPException(
            status_code=400,
            detail="Ukuran file maksimal 5 MB",
        )

    # Bikin nama file unik supaya tidak tabrakan
    extension = file.content_type.split("/")[-1]
    if extension == "jpeg":
        extension = "jpg"
    filename = f"{uuid.uuid4().hex}.{extension}"
    filepath = UPLOAD_DIR / filename

    with open(filepath, "wb") as f:
        f.write(contents)

    # Hapus avatar lama supaya file tidak menumpuk
    if current_user.avatar_url:
        old_path = Path(current_user.avatar_url.lstrip("/"))
        if old_path.exists() and old_path.is_file():
            try:
                old_path.unlink()
            except OSError:
                pass

    current_user.avatar_url = f"/uploads/{filename}"
    db.commit()
    db.refresh(current_user)
    return current_user

@app.get("/dashboard", response_model=schemas.DashboardResponse)
def get_dashboard(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Self-healing: kalau streak/wallet belum ada (user lama), bikinkan
    streak = db.query(models.Streak).filter(
        models.Streak.user_id == current_user.id
    ).first()
    if not streak:
        streak = models.Streak(user_id=current_user.id)
        db.add(streak)
        db.commit()
        db.refresh(streak)

    wallet = db.query(models.Wallet).filter(
        models.Wallet.user_id == current_user.id
    ).first()
    if not wallet:
        wallet = models.Wallet(user_id=current_user.id)
        db.add(wallet)
        db.commit()
        db.refresh(wallet)

    return {
        "username": current_user.username,
        "avatar_url": current_user.avatar_url,
        "current_streak": streak.current_streak,
        "coin_balance": wallet.coin_balance,
        "is_new_user": streak.last_completed_date is None,
    }

def generate_join_code(length: int = 6) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


@app.post("/ecosystem", response_model=schemas.EcosystemResponse)
def create_ecosystem(
    req: schemas.EcosystemCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.ecosystem_id:
        raise HTTPException(
            status_code=400,
            detail="Kamu sudah tergabung di ekosistem lain. Keluar dulu sebelum bikin baru.",
        )

    # Bikin kode unik, coba ulang kalau kebetulan kembar
    for _ in range(10):
        code = generate_join_code()
        existing = db.query(models.Ecosystem).filter(
            models.Ecosystem.join_code == code
        ).first()
        if not existing:
            break
    else:
        raise HTTPException(status_code=500, detail="Gagal membuat kode unik")

    ecosystem = models.Ecosystem(name=req.name, join_code=code)
    db.add(ecosystem)
    db.commit()
    db.refresh(ecosystem)

    # Otomatis masukkan pembuat ke ekosistem ini
    current_user.ecosystem_id = ecosystem.id
    db.commit()

    members = db.query(models.User).filter(
        models.User.ecosystem_id == ecosystem.id
    ).all()

    return {
        "id": ecosystem.id,
        "name": ecosystem.name,
        "join_code": ecosystem.join_code,
        "members": members,
    }


@app.post("/ecosystem/join", response_model=schemas.EcosystemResponse)
def join_ecosystem(
    req: schemas.EcosystemJoin,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.ecosystem_id:
        raise HTTPException(
            status_code=400,
            detail="Kamu sudah tergabung di ekosistem lain. Keluar dulu sebelum join.",
        )

    ecosystem = db.query(models.Ecosystem).filter(
        models.Ecosystem.join_code == req.join_code
    ).first()
    if not ecosystem:
        raise HTTPException(status_code=404, detail="Kode tidak ditemukan")

    current_user.ecosystem_id = ecosystem.id
    db.commit()

    members = db.query(models.User).filter(
        models.User.ecosystem_id == ecosystem.id
    ).all()

    return {
        "id": ecosystem.id,
        "name": ecosystem.name,
        "join_code": ecosystem.join_code,
        "members": members,
    }


@app.get("/ecosystem", response_model=schemas.EcosystemResponse)
def get_ecosystem(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.ecosystem_id:
        raise HTTPException(
            status_code=404,
            detail="Kamu belum tergabung di ekosistem manapun",
        )

    ecosystem = db.query(models.Ecosystem).filter(
        models.Ecosystem.id == current_user.ecosystem_id
    ).first()

    members = db.query(models.User).filter(
        models.User.ecosystem_id == ecosystem.id
    ).all()

    return {
        "id": ecosystem.id,
        "name": ecosystem.name,
        "join_code": ecosystem.join_code,
        "members": members,
    }

COINS_PER_QUEST = 10


@app.post("/quest/start", response_model=schemas.QuestStartResponse)
def start_quest(
    mood: schemas.MoodInput,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    active = db.query(models.QuestSession).filter(
        models.QuestSession.user_id == current_user.id,
        models.QuestSession.status.in_(["mood_check", "active"]),
    ).first()
    if active:
        raise HTTPException(status_code=400, detail="Masih ada quest aktif yang belum selesai")

    session = models.QuestSession(user_id=current_user.id, status="mood_check")
    db.add(session)
    db.commit()
    db.refresh(session)

    mood_log = models.MoodLog(
        user_id=current_user.id,
        session_id=session.id,
        mood_before=mood.mood,
    )
    db.add(mood_log)
    db.commit()

    if mood.mood == 1:
        return {"session_id": session.id, "message": "decision_bridge"}

    return {"session_id": session.id, "message": "ready"}

@app.post("/quest/{session_id}/mental-break")
def take_mental_break(
    session_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(models.QuestSession).filter(
        models.QuestSession.id == session_id,
        models.QuestSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Quest tidak ditemukan")

    session.status = "break"
    db.commit()

    mood_log = db.query(models.MoodLog).filter(
        models.MoodLog.session_id == session_id
    ).first()
    if mood_log:
        mood_log.took_break = True
        db.commit()

    return {"message": "Istirahat dulu ya. Streak kamu aman hari ini."}

@app.post("/quest/{session_id}/before-image", response_model=schemas.QuestSessionResponse)
async def upload_before_image(
    session_id: int,
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(models.QuestSession).filter(
        models.QuestSession.id == session_id,
        models.QuestSession.user_id == current_user.id,
        models.QuestSession.status == "mood_check",
    ).first()
    if not session:
        raise HTTPException(status_code=400, detail="Quest tidak dalam status yang benar")

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Format file harus JPG, PNG, atau WEBP")

    contents = await file.read()
    if len(contents) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=400, detail="Ukuran file maksimal 5 MB")

    extension = file.content_type.split("/")[-1]
    if extension == "jpeg":
        extension = "jpg"
    filename = f"before_{uuid.uuid4().hex}.{extension}"
    filepath = UPLOAD_DIR / filename
    with open(filepath, "wb") as f:
        f.write(contents)

    # Simulasi YOLOv8
    analysis = analyze_room_image(str(filepath))

    session.before_image_url = f"/uploads/{filename}"
    session.hoarding_index_before = analysis["hoarding_index"]
    session.target_items = analysis["target_items"]
    session.status = "active"
    db.commit()

    # Simulasi LLM — generate langkah atomik
    steps = generate_atomic_steps(analysis["target_items"])
    for i, instruction in enumerate(steps):
        step = models.QuestStep(
            session_id=session.id,
            order_index=i + 1,
            instruction=instruction,
        )
        db.add(step)
    db.commit()
    db.refresh(session)

    return session

@app.get("/quest/{session_id}/steps", response_model=list[schemas.QuestStepResponse])
def get_quest_steps(
    session_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(models.QuestSession).filter(
        models.QuestSession.id == session_id,
        models.QuestSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Quest tidak ditemukan")

    steps = db.query(models.QuestStep).filter(
        models.QuestStep.session_id == session_id
    ).order_by(models.QuestStep.order_index).all()

    return steps


@app.patch("/quest/{session_id}/steps/{step_id}/done", response_model=schemas.QuestStepResponse)
def mark_step_done(
    session_id: int,
    step_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(models.QuestSession).filter(
        models.QuestSession.id == session_id,
        models.QuestSession.user_id == current_user.id,
        models.QuestSession.status == "active",
    ).first()
    if not session:
        raise HTTPException(status_code=400, detail="Quest tidak aktif")
    step = db.query(models.QuestStep).filter(
        models.QuestStep.id == step_id,
        models.QuestStep.session_id == session_id,
    ).first()
    if not step:
        raise HTTPException(status_code=404, detail="Step tidak ditemukan")
    step.is_done = True
    db.commit()
    db.refresh(step)
    return step

@app.post("/quest/{session_id}/after-image", response_model=schemas.QuestSessionResponse)
async def upload_after_image(
    session_id: int,
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(models.QuestSession).filter(
        models.QuestSession.id == session_id,
        models.QuestSession.user_id == current_user.id,
        models.QuestSession.status == "active",
    ).first()
    if not session:
        raise HTTPException(status_code=400, detail="Quest tidak dalam status yang benar")

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Format file harus JPG, PNG, atau WEBP")

    contents = await file.read()
    if len(contents) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=400, detail="Ukuran file maksimal 5 MB")

    extension = file.content_type.split("/")[-1]
    if extension == "jpeg":
        extension = "jpg"
    filename = f"after_{uuid.uuid4().hex}.{extension}"
    filepath = UPLOAD_DIR / filename
    with open(filepath, "wb") as f:
        f.write(contents)

    comparison = compare_before_after(
        session.before_image_url or "",
        str(filepath),
    )

    session.after_image_url = f"/uploads/{filename}"
    session.hoarding_index_after = max(
        0, session.hoarding_index_before - comparison["improvement_percent"] // 10
    )
    db.commit()
    db.refresh(session)

    if not comparison["is_valid"]:
        raise HTTPException(
            status_code=400,
            detail="Hmm, sepertinya belum ada perubahan signifikan. Coba rapikan lagi ya!",
        )

    return session

@app.post("/quest/{session_id}/complete", response_model=schemas.QuestCompleteResponse)
def complete_quest(
    session_id: int,
    req: schemas.QuestCompleteRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(models.QuestSession).filter(
        models.QuestSession.id == session_id,
        models.QuestSession.user_id == current_user.id,
        models.QuestSession.status == "active",
    ).first()
    if not session:
        raise HTTPException(status_code=400, detail="Quest tidak dalam status yang benar")
    mood_log = db.query(models.MoodLog).filter(
        models.MoodLog.session_id == session_id
    ).first()
    if mood_log:
        mood_log.mood_after = req.mood_after
    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    db.commit()
    streak = db.query(models.Streak).filter(
        models.Streak.user_id == current_user.id
    ).first()
    if not streak:
        streak = models.Streak(user_id=current_user.id)
        db.add(streak)
        db.commit()
        db.refresh(streak)
    from datetime import date
    today = date.today()
    if streak.last_completed_date == today:
        pass
    elif streak.last_completed_date == today - timedelta(days=1):
        streak.current_streak += 1
    else:
        streak.current_streak = 1
    if streak.current_streak > streak.longest_streak:
        streak.longest_streak = streak.current_streak
    streak.last_completed_date = today
    wallet = db.query(models.Wallet).filter(
        models.Wallet.user_id == current_user.id
    ).first()
    if not wallet:
        wallet = models.Wallet(user_id=current_user.id)
        db.add(wallet)
        db.commit()
        db.refresh(wallet)
    wallet.coin_balance += COINS_PER_QUEST
    db.commit()

    # Auto-award badge berdasarkan streak
    all_badges = db.query(models.Badge).all()
    for badge in all_badges:
        if streak.current_streak >= badge.criteria_streak:
            already = db.query(models.UserBadge).filter(
                models.UserBadge.user_id == current_user.id,
                models.UserBadge.badge_id == badge.id,
            ).first()
            if not already:
                db.add(models.UserBadge(user_id=current_user.id, badge_id=badge.id))
    db.commit()

    # Update AI Assistant
    assistant = db.query(models.AIAssistant).filter(
        models.AIAssistant.user_id == current_user.id
    ).first()
    if not assistant:
        assistant = models.AIAssistant(user_id=current_user.id)
        db.add(assistant)
    assistant.total_quests_completed += 1
    db.commit()
    return {
        "message": "Quest selesai! Hebat!",
        "coins_earned": COINS_PER_QUEST,
        "current_streak": streak.current_streak,
        "mood_before": mood_log.mood_before if mood_log else 0,
        "mood_after": req.mood_after,
        "improvement_percent": max(0, (session.hoarding_index_before or 0) - (session.hoarding_index_after or 0)) * 10,
    }

@app.get("/leaderboard", response_model=list[schemas.LeaderboardEntry])
def get_leaderboard(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.ecosystem_id:
        raise HTTPException(
            status_code=404,
            detail="Kamu belum tergabung di ekosistem manapun",
        )

    members = db.query(models.User).filter(
        models.User.ecosystem_id == current_user.ecosystem_id
    ).all()

    entries = []
    for member in members:
        streak = db.query(models.Streak).filter(
            models.Streak.user_id == member.id
        ).first()
        wallet = db.query(models.Wallet).filter(
            models.Wallet.user_id == member.id
        ).first()
        entries.append({
            "username": member.username,
            "avatar_url": member.avatar_url,
            "current_streak": streak.current_streak if streak else 0,
            "coin_balance": wallet.coin_balance if wallet else 0,
        })

    entries.sort(key=lambda x: (x["current_streak"], x["coin_balance"]), reverse=True)
    entries = entries[:10]

    for i, entry in enumerate(entries):
        entry["rank"] = i + 1

    return entries

@app.get("/rewards", response_model=list[schemas.RewardResponse])
def get_rewards(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wallet = db.query(models.Wallet).filter(
        models.Wallet.user_id == current_user.id
    ).first()
    balance = wallet.coin_balance if wallet else 0

    rewards = db.query(models.Reward).all()
    result = []
    for r in rewards:
        result.append({
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "reward_type": r.reward_type,
            "cost_coins": r.cost_coins,
            "image_url": r.image_url,
            "can_claim": balance >= r.cost_coins,
        })
    return result


@app.post("/rewards/{reward_id}/claim", response_model=schemas.RewardClaimResponse)
def claim_reward(
    reward_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reward = db.query(models.Reward).filter(models.Reward.id == reward_id).first()
    if not reward:
        raise HTTPException(status_code=404, detail="Hadiah tidak ditemukan")

    wallet = db.query(models.Wallet).filter(
        models.Wallet.user_id == current_user.id
    ).first()
    if not wallet or wallet.coin_balance < reward.cost_coins:
        raise HTTPException(status_code=400, detail="Koin tidak cukup")

    wallet.coin_balance -= reward.cost_coins
    claim = models.RewardClaim(user_id=current_user.id, reward_id=reward.id)
    db.add(claim)
    db.commit()

    return {
        "message": f"Berhasil klaim {reward.name}!",
        "reward_name": reward.name,
        "coin_balance": wallet.coin_balance,
    }

@app.get("/badges", response_model=list[schemas.BadgeResponse])
def get_badges(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    badges = db.query(models.Badge).order_by(models.Badge.criteria_streak).all()
    earned_ids = {
        ub.badge_id
        for ub in db.query(models.UserBadge).filter(
            models.UserBadge.user_id == current_user.id
        ).all()
    }

    result = []
    for b in badges:
        result.append({
            "id": b.id,
            "name": b.name,
            "description": b.description,
            "criteria_streak": b.criteria_streak,
            "icon_url": b.icon_url,
            "earned": b.id in earned_ids,
        })
    return result

@app.get("/streak", response_model=schemas.StreakResponse)
def get_streak(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    streak = db.query(models.Streak).filter(
        models.Streak.user_id == current_user.id
    ).first()
    if not streak:
        streak = models.Streak(user_id=current_user.id)
        db.add(streak)
        db.commit()
        db.refresh(streak)

    # Cari badge berikutnya yang belum didapat
    earned_ids = {
        ub.badge_id
        for ub in db.query(models.UserBadge).filter(
            models.UserBadge.user_id == current_user.id
        ).all()
    }
    next_badge = db.query(models.Badge).filter(
        models.Badge.id.notin_(earned_ids)
    ).order_by(models.Badge.criteria_streak).first()

    return {
        "current_streak": streak.current_streak,
        "longest_streak": streak.longest_streak,
        "last_completed_date": str(streak.last_completed_date) if streak.last_completed_date else None,
        "next_badge_name": next_badge.name if next_badge else None,
        "next_badge_streak": next_badge.criteria_streak if next_badge else None,
        "days_to_next_badge": max(0, next_badge.criteria_streak - streak.current_streak) if next_badge else None,
    }

@app.get("/mood-history", response_model=list[schemas.MoodHistoryEntry])
def get_mood_history(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    logs = db.query(models.MoodLog).filter(
        models.MoodLog.user_id == current_user.id,
        models.MoodLog.mood_after.isnot(None),
    ).order_by(models.MoodLog.created_at.desc()).all()

    result = []
    for log in logs:
        result.append({
            "session_id": log.session_id,
            "mood_before": log.mood_before,
            "mood_after": log.mood_after,
            "mood_change": (log.mood_after or 0) - (log.mood_before or 0),
            "took_break": log.took_break,
            "created_at": str(log.created_at),
        })
    return result

EVOLUTION_THRESHOLDS = [
    (1, "Bibit"),
    (5, "Tunas"),
    (15, "Tanaman Muda"),
    (30, "Pohon Rindang"),
    (50, "Pohon Berbuah"),
]


def get_evolution(total_quests: int) -> tuple[int, str, int | None]:
    level = 1
    name = EVOLUTION_THRESHOLDS[0][1]
    next_at = EVOLUTION_THRESHOLDS[1][0] if len(EVOLUTION_THRESHOLDS) > 1 else None
    for i, (threshold, evo_name) in enumerate(EVOLUTION_THRESHOLDS):
        if total_quests >= threshold:
            level = i + 1
            name = evo_name
            next_at = EVOLUTION_THRESHOLDS[i + 1][0] if i + 1 < len(EVOLUTION_THRESHOLDS) else None
    return level, name, next_at


@app.get("/assistant", response_model=schemas.AIAssistantResponse)
def get_assistant(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assistant = db.query(models.AIAssistant).filter(
        models.AIAssistant.user_id == current_user.id
    ).first()
    if not assistant:
        assistant = models.AIAssistant(user_id=current_user.id)
        db.add(assistant)
        db.commit()
        db.refresh(assistant)

    level, name, next_at = get_evolution(assistant.total_quests_completed)
    assistant.evolution_level = level
    db.commit()

    return {
        "evolution_level": level,
        "total_quests_completed": assistant.total_quests_completed,
        "next_evolution_at": next_at,
        "evolution_name": name,
    }

@app.post("/auth/google", response_model=schemas.TokenResponse)
def google_login(req: schemas.SocialLoginRequest, db: Session = Depends(get_db)):
    try:
        idinfo = google_id_token.verify_oauth2_token(
            req.id_token,
            google_requests.Request(),
        )
        email = idinfo.get("email")
        name = idinfo.get("name", "")
        if not email:
            raise HTTPException(status_code=400, detail="Token Google tidak mengandung email")
    except ValueError:
        raise HTTPException(status_code=401, detail="Token Google tidak valid")

    # Cek apakah user sudah ada
    user = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        # Buat user baru — password di-hash random karena login via Google
        import secrets
        random_password = secrets.token_urlsafe(32)
        username = email.split("@")[0]

        # Pastikan username unik
        base_username = username
        counter = 1
        while db.query(models.User).filter(models.User.username == username).first():
            username = f"{base_username}{counter}"
            counter += 1

        user = models.User(
            email=email,
            username=username,
            password_hash=hash_password(random_password),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Bikin streak dan wallet default
        db.add(models.Streak(user_id=user.id))
        db.add(models.Wallet(user_id=user.id))
        db.commit()

    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer"}
    