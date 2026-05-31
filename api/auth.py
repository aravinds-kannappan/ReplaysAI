"""
User profile, favorites, and notification endpoints.
All require Clerk JWT auth via get_current_user dependency.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.models import (
    Badge, Notification, Team, Player, User,
    UserBadge, UserFavoriteTeam, UserFollowedPlayer, UserPoints, UserStreak,
)
from db.session import get_db
from middleware.clerk_auth import get_current_user

router = APIRouter(prefix="/api/users", tags=["users"])


def _serialize_user(user: User) -> dict:
    points = user.points
    streak = user.streaks
    fav_teams = [{"id": ft.team_id, "name": ft.team.name, "abbreviation": ft.team.abbreviation, "sport": ft.team.sport} for ft in user.favorite_teams]
    badges = [{"slug": ub.badge.slug, "name": ub.badge.name, "icon": ub.badge.icon, "earned_at": ub.earned_at.isoformat()} for ub in user.badges]
    return {
        "id": user.id,
        "clerk_id": user.clerk_id,
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "avatar_url": user.avatar_url,
        "bio": user.bio,
        "favorite_teams": fav_teams,
        "total_points": points.total_points if points else 0,
        "login_streak": streak.login_streak if streak else 0,
        "prediction_accuracy": (
            round(streak.correct_predictions / streak.total_predictions * 100, 1)
            if streak and streak.total_predictions > 0 else 0
        ),
        "badges": badges,
        "onboarded": bool(user.favorite_teams),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _update_login_streak(user: User, db: Session) -> None:
    streak = user.streaks
    if not streak:
        return
    today = date.today()
    if streak.last_login_date == today:
        return  # already logged in today
    if streak.last_login_date and (today - streak.last_login_date).days == 1:
        streak.login_streak += 1
    else:
        streak.login_streak = 1
    streak.longest_login_streak = max(streak.login_streak, streak.longest_login_streak)
    streak.last_login_date = today

    # Award streak points
    if user.points:
        user.points.engagement_points += 5
        user.points.total_points += 5
        if streak.login_streak == 7:
            user.points.streak_bonus_points += 25
            user.points.total_points += 25
            _maybe_award_badge(user, "loyal", db)
        if streak.login_streak == 30:
            _maybe_award_badge(user, "superfan", db)
    db.commit()


def _maybe_award_badge(user: User, slug: str, db: Session) -> None:
    badge = db.query(Badge).filter_by(slug=slug).first()
    if not badge:
        return
    already = db.query(UserBadge).filter_by(user_id=user.id, badge_id=badge.id).first()
    if not already:
        db.add(UserBadge(user_id=user.id, badge_id=badge.id))
        db.commit()


@router.get("/me")
def get_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _update_login_streak(user, db)
    db.refresh(user)
    return _serialize_user(user)


class UpdateProfileBody(BaseModel):
    username: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None


@router.put("/me")
def update_profile(body: UpdateProfileBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.username is not None:
        existing = db.query(User).filter(User.username == body.username, User.id != user.id).first()
        if existing:
            raise HTTPException(status_code=409, detail="Username taken")
        user.username = body.username
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.bio is not None:
        user.bio = body.bio
    if body.avatar_url is not None:
        user.avatar_url = body.avatar_url
    db.commit()
    db.refresh(user)
    return _serialize_user(user)


@router.get("/me/teams")
def get_favorite_teams(user: User = Depends(get_current_user)):
    return [{"id": ft.team_id, "name": ft.team.name, "abbreviation": ft.team.abbreviation, "sport": ft.team.sport} for ft in user.favorite_teams]


class TeamBody(BaseModel):
    team_id: int


@router.post("/me/teams")
def add_favorite_team(body: TeamBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    team = db.query(Team).get(body.team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    existing = db.query(UserFavoriteTeam).filter_by(user_id=user.id, team_id=body.team_id).first()
    if not existing:
        db.add(UserFavoriteTeam(user_id=user.id, team_id=body.team_id))
        # Award first follow badge engagement
        if user.points:
            user.points.engagement_points += 5
            user.points.total_points += 5
        db.commit()
    return {"status": "ok"}


@router.delete("/me/teams/{team_id}")
def remove_favorite_team(team_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(UserFavoriteTeam).filter_by(user_id=user.id, team_id=team_id).delete()
    db.commit()
    return {"status": "ok"}


class PlayerBody(BaseModel):
    player_id: int


@router.post("/me/players")
def follow_player(body: PlayerBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    player = db.query(Player).get(body.player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    existing = db.query(UserFollowedPlayer).filter_by(user_id=user.id, player_id=body.player_id).first()
    if not existing:
        db.add(UserFollowedPlayer(user_id=user.id, player_id=body.player_id))
        db.commit()
    return {"status": "ok"}


@router.delete("/me/players/{player_id}")
def unfollow_player(player_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(UserFollowedPlayer).filter_by(user_id=user.id, player_id=player_id).delete()
    db.commit()
    return {"status": "ok"}


@router.get("/me/notifications")
def get_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notifs = db.query(Notification).filter_by(user_id=user.id).order_by(Notification.created_at.desc()).limit(30).all()
    return [{"id": n.id, "type": n.type, "title": n.title, "body": n.body, "read": n.read, "game_id": n.game_id, "created_at": n.created_at.isoformat()} for n in notifs]


@router.post("/me/notifications/{notif_id}/read")
def mark_read(notif_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.query(Notification).filter_by(id=notif_id, user_id=user.id).first()
    if n:
        n.read = True
        db.commit()
    return {"status": "ok"}
