from datetime import date, timedelta
from database import SessionLocal
import models


def reset_expired_streaks():
    """Jalan tiap hari jam 00:00 — reset streak yang tidak aktif kemarin."""
    db = SessionLocal()
    try:
        yesterday = date.today() - timedelta(days=1)
        expired = db.query(models.Streak).filter(
            models.Streak.current_streak > 0,
            models.Streak.last_completed_date < yesterday,
        ).all()

        count = 0
        for streak in expired:
            streak.current_streak = 0
            count += 1

        db.commit()
        print(f"[CRON] Streak reset: {count} user direset")
    finally:
        db.close()