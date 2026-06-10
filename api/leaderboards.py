"""
Leaderboard endpoints.
Without database storage, leaderboard history is not persisted server-side.
"""
from fastapi import APIRouter, Depends

from middleware.clerk_auth import AuthUser, get_current_user

router = APIRouter(prefix="/api", tags=["leaderboard"])


@router.get("/leaderboard")
def get_leaderboard(_limit: int = 50):
    return []


@router.get("/leaderboard/me")
def get_my_rank(user: AuthUser = Depends(get_current_user)):
    return {
        "my_rank": 1,
        "total_users": 1,
        "neighbors": [{
            "rank": 1,
            "user_id": user.id,
            "username": user.username or "you",
            "display_name": user.display_name or user.username or "You",
            "avatar_url": user.avatar_url,
            "total_points": 0,
            "correct_predictions": 0,
            "total_predictions": 0,
            "accuracy": 0,
            "login_streak": 0,
            "badges": [],
        }],
    }
