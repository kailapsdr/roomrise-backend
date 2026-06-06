import re
from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRegister(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=30)
    password: str = Field(min_length=8)
    confirm_password: str = Field(min_length=8)
    captcha_token: str | None = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password harus mengandung huruf besar")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password harus mengandung huruf kecil")
        if not re.search(r"\d", v):
            raise ValueError("Password harus mengandung angka")
        if not re.search(r"[!@#$%^&*()\-_=+\[\]{};:'\",.<>/?\\|`~]", v):
            raise ValueError("Password harus mengandung simbol")
        return v

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        password = info.data.get("password")
        if password and v != password:
            raise ValueError("Kedua password harus sesuai")
        return v


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    username: str
    avatar_url: str | None = None

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password harus mengandung huruf besar")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password harus mengandung huruf kecil")
        if not re.search(r"\d", v):
            raise ValueError("Password harus mengandung angka")
        if not re.search(r"[!@#$%^&*()\-_=+\[\]{};:'\",.<>/?\\|`~]", v):
            raise ValueError("Password harus mengandung simbol")
        return v


class UsernameUpdateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=30)


class LeaderboardEntry(BaseModel):
    rank: int
    username: str
    avatar_url: str | None = None
    current_streak: int
    coin_balance: int


class DashboardResponse(BaseModel):
    username: str
    avatar_url: str | None = None
    current_streak: int
    coin_balance: int
    is_new_user: bool
    top_leaderboard: list[LeaderboardEntry] = []


class EcosystemCreate(BaseModel):
    name: str = Field(min_length=3, max_length=50)


class EcosystemJoin(BaseModel):
    join_code: str


class EcosystemMember(BaseModel):
    id: int
    username: str
    avatar_url: str | None = None

    class Config:
        from_attributes = True


class EcosystemResponse(BaseModel):
    id: int
    name: str
    join_code: str
    members: list[EcosystemMember]

    class Config:
        from_attributes = True


class MoodInput(BaseModel):
    mood: int = Field(ge=1, le=5)


class QuestStartResponse(BaseModel):
    session_id: int
    message: str


class QuestSessionResponse(BaseModel):
    id: int
    status: str
    before_image_url: str | None = None
    after_image_url: str | None = None
    hoarding_index_before: int | None = None
    hoarding_index_after: int | None = None
    target_items: int | None = None

    class Config:
        from_attributes = True


class QuestStepResponse(BaseModel):
    id: int
    order_index: int
    instruction: str
    is_done: bool

    class Config:
        from_attributes = True


class DecisionBridgeResponse(BaseModel):
    needs_break: bool
    message: str


class QuestCompleteRequest(BaseModel):
    mood_after: int = Field(ge=1, le=5)


class QuestCompleteResponse(BaseModel):
    message: str
    coins_earned: int
    current_streak: int
    mood_before: int
    mood_after: int
    improvement_percent: int


class RewardResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    reward_type: str
    cost_coins: int
    image_url: str | None = None
    can_claim: bool

    class Config:
        from_attributes = True


class RewardClaimResponse(BaseModel):
    message: str
    reward_name: str
    coin_balance: int


class BadgeResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    criteria_streak: int
    icon_url: str | None = None
    earned: bool

    class Config:
        from_attributes = True


class StreakResponse(BaseModel):
    current_streak: int
    longest_streak: int
    last_completed_date: str | None = None
    next_badge_name: str | None = None
    next_badge_streak: int | None = None
    days_to_next_badge: int | None = None


class MoodHistoryEntry(BaseModel):
    session_id: int
    mood_before: int | None = None
    mood_after: int | None = None
    mood_change: int
    took_break: bool
    created_at: str


class AIAssistantResponse(BaseModel):
    evolution_level: int
    total_quests_completed: int
    next_evolution_at: int | None = None
    evolution_name: str


class SocialLoginRequest(BaseModel):
    id_token: str