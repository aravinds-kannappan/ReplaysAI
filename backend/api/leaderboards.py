"""
Leaderboard endpoints.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.db.models import User, UserPoints, UserStreak
from backend.db.session import get_db
from backend.middleware.clerk_auth import get_current_user

router = APIRouter(prefix="/api", tags=["leaderboard"])


def _serialize_entry(rank: int, user: User) -> dict:
    pts = user.points
    streak = user.streaks
    return {
        "rank": rank,
        "user_id": user.id,
        "username": user.username or f"fan_{user.id}",
        "display_name": user.display_name or user.username or f"Fan #{user.id}",
        "avatar_url": user.avatar_url,
        "total_points": pts.total_points if pts else 0,
        "correct_predictions": streak.correct_predictions if streak else 0,
        "total_predictions": streak.total_predictions if streak else 0,
        "accuracy": (
            round(streak.correct_predictions / streak.total_predictions * 100, 1)
            if streak and streak.total_predictions > 0 else 0
        ),
        "login_streak": streak.login_streak if streak else 0,
        "badges": [{"slug": ub.badge.slug, "icon": ub.badge.icon} for ub in user.badges],
    }


@router.get("/leaderboard")
def get_leaderboard(limit: int = 50, db: Session = Depends(get_db)):
    users = (
        db.query(User)
        .join(UserPoints, User.id == UserPoints.user_id, isouter=True)
        .order_by(UserPoints.total_points.desc().nulls_last())
        .limit(limit)
        .all()
    )
    return [_serialize_entry(i + 1, u) for i, u in enumerate(users)]


@router.get("/leaderboard/me")
def get_my_rank(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    all_users = (
        db.query(User)
        .join(UserPoints, User.id == UserPoints.user_id, isouter=True)
        .order_by(UserPoints.total_points.desc().nulls_last())
        .all()
    )
    my_rank = next((i + 1 for i, u in enumerate(all_users) if u.id == user.id), len(all_users))
    start = max(0, my_rank - 3)
    neighbors = all_users[start: my_rank + 2]
    return {
        "my_rank": my_rank,
        "total_users": len(all_users),
        "neighbors": [_serialize_entry(start + i + 1, u) for i, u in enumerate(neighbors)],
    }
