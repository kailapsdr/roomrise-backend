from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from database import Base
from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey
from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, Boolean


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    avatar_url = Column(String, nullable=True)
    ecosystem_id = Column(Integer, ForeignKey("ecosystems.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PasswordReset(Base):
    __tablename__ = "password_resets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    otp = Column(String, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Streak(Base):
    __tablename__ = "streaks"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    current_streak = Column(Integer, nullable=False, default=0)
    longest_streak = Column(Integer, nullable=False, default=0)
    last_completed_date = Column(Date, nullable=True)


class Wallet(Base):
    __tablename__ = "wallets"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    coin_balance = Column(Integer, nullable=False, default=0)

class Ecosystem(Base):
    __tablename__ = "ecosystems"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    join_code = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class QuestSession(Base):
    __tablename__ = "quest_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default="pending")
    before_image_url = Column(String, nullable=True)
    after_image_url = Column(String, nullable=True)
    hoarding_index_before = Column(Integer, nullable=True)
    hoarding_index_after = Column(Integer, nullable=True)
    target_items = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class QuestStep(Base):
    __tablename__ = "quest_steps"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("quest_sessions.id"), nullable=False, index=True)
    order_index = Column(Integer, nullable=False)
    instruction = Column(String, nullable=False)
    is_done = Column(Boolean, nullable=False, default=False)


class MoodLog(Base):
    __tablename__ = "mood_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("quest_sessions.id"), nullable=False)
    mood_before = Column(Integer, nullable=True)
    mood_after = Column(Integer, nullable=True)
    took_break = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Reward(Base):
    __tablename__ = "rewards"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    reward_type = Column(String, nullable=False)  # "virtual" atau "physical"
    cost_coins = Column(Integer, nullable=False)
    image_url = Column(String, nullable=True)


class RewardClaim(Base):
    __tablename__ = "reward_claims"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    reward_id = Column(Integer, ForeignKey("rewards.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Badge(Base):
    __tablename__ = "badges"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    criteria_streak = Column(Integer, nullable=False)
    icon_url = Column(String, nullable=True)


class UserBadge(Base):
    __tablename__ = "user_badges"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    badge_id = Column(Integer, ForeignKey("badges.id"), nullable=False)
    earned_at = Column(DateTime(timezone=True), server_default=func.now())

class AIAssistant(Base):
    __tablename__ = "ai_assistants"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    evolution_level = Column(Integer, nullable=False, default=1)
    total_quests_completed = Column(Integer, nullable=False, default=0)