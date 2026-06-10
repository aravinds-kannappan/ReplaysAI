"""
User profile endpoints backed by Clerk and client-side personalization state.
No database is required for Vercel deployment.
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from middleware.clerk_auth import AuthUser, get_current_user

router = APIRouter(prefix="/api/users", tags=["users"])


def _serialize_user(user: AuthUser) -> dict:
    return {
        "id": user.id,
        "clerk_id": user.clerk_id,
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "avatar_url": user.avatar_url,
        "bio": user.bio,
        "favorite_teams": [],
        "followed_players": [],
        "total_points": 0,
        "login_streak": 0,
        "prediction_accuracy": 0,
        "badges": [],
        "onboarded": False,
        "created_at": None,
    }


@router.get("/me")
def get_me(user: AuthUser = Depends(get_current_user)):
    return _serialize_user(user)


class UpdateProfileBody(BaseModel):
    username: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None


@router.put("/me")
def update_profile(body: UpdateProfileBody, user: AuthUser = Depends(get_current_user)):
    updated = _serialize_user(user)
    for field in ("username", "display_name", "bio", "avatar_url"):
        value = getattr(body, field)
        if value is not None:
            updated[field] = value
    return updated


@router.get("/me/teams")
def get_favorite_teams():
    return []


class TeamBody(BaseModel):
    team_id: int
    sport: Optional[str] = None


@router.post("/me/teams")
def add_favorite_team(_body: TeamBody, _user: AuthUser = Depends(get_current_user)):
    return {"status": "ok", "storage": "client"}


@router.delete("/me/teams/{team_id}")
def remove_favorite_team(_team_id: int, _user: AuthUser = Depends(get_current_user)):
    return {"status": "ok", "storage": "client"}


class PlayerBody(BaseModel):
    player_id: int


@router.post("/me/players")
def follow_player(_body: PlayerBody, _user: AuthUser = Depends(get_current_user)):
    return {"status": "ok", "storage": "client"}


@router.delete("/me/players/{player_id}")
def unfollow_player(_player_id: int, _user: AuthUser = Depends(get_current_user)):
    return {"status": "ok", "storage": "client"}


@router.get("/me/notifications")
def get_notifications(_user: AuthUser = Depends(get_current_user)):
    return []


@router.post("/me/notifications/{notif_id}/read")
def mark_read(_notif_id: int, _user: AuthUser = Depends(get_current_user)):
    return {"status": "ok"}
