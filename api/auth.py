"""
Anonymous profile endpoints.

Identity is the device id (middleware/identity.py); teams and followed players
live client-side in localStorage. The server owns only the earned state: points,
streak, badges, and prediction accuracy, read from the Redis store (db/store.py).
Zeros when no REDIS_URL is configured.
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from middleware.identity import AuthUser, get_current_user
from db import store

router = APIRouter(prefix="/api/users", tags=["users"])


def _serialize(user: AuthUser) -> dict:
    profile = store.get_profile(user.id)
    return {
        "id": user.id,
        "device_id": user.device_id,
        "display_name": profile.get("display_name") or user.display_name,
        "favorite_teams": [],       # owned client-side
        "followed_players": [],     # owned client-side
        "total_points": profile["total_points"],
        "login_streak": profile["login_streak"],
        "best_streak": profile["best_streak"],
        "prediction_accuracy": profile["prediction_accuracy"],
        "correct_predictions": profile["correct_predictions"],
        "total_predictions": profile["total_predictions"],
        "badges": profile["badges"],
        "onboarded": False,
    }


@router.get("/me")
def get_me(user: AuthUser = Depends(get_current_user)):
    return _serialize(user)


class UpdateProfileBody(BaseModel):
    display_name: Optional[str] = None


@router.put("/me")
def update_profile(body: UpdateProfileBody, user: AuthUser = Depends(get_current_user)):
    if body.display_name:
        store.set_display_name(user.id, body.display_name)
    return _serialize(user)
