"""
Personalized feed and fan-perspective recap endpoints.
"""
import asyncio
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.agents.fan_perspective import fan_perspective_agent
from backend.cache.redis_client import cache_get, cache_set
from backend.db.models import FanRecap, Game, User, UserFavoriteTeam
from backend.db.session import get_db
from backend.middleware.clerk_auth import get_current_user

router = APIRouter(prefix="/api", tags=["feed"])

_fan_recap_locks: dict[str, bool] = {}


def _serialize_game(g: Game) -> dict:
    return {
        "id": g.id,
        "sport": g.sport,
        "status": g.status,
        "game_date": g.game_date.isoformat() if g.game_date else None,
        "home_team": {"id": g.home_team_id, "name": g.home_team.name if g.home_team else None, "abbreviation": g.home_team.abbreviation if g.home_team else None},
        "away_team": {"id": g.away_team_id, "name": g.away_team.name if g.away_team else None, "abbreviation": g.away_team.abbreviation if g.away_team else None},
        "home_score": g.home_score,
        "away_score": g.away_score,
        "video_url": g.video_url,
    }


@router.get("/feed")
def get_personalized_feed(
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    favorite_team_ids = [ft.team_id for ft in user.favorite_teams]

    if not favorite_team_ids:
        # Not onboarded yet — return recent games
        games = db.query(Game).order_by(Game.game_date.desc()).limit(limit).all()
    else:
        games = (
            db.query(Game)
            .filter(
                (Game.home_team_id.in_(favorite_team_ids)) |
                (Game.away_team_id.in_(favorite_team_ids))
            )
            .order_by(Game.game_date.desc())
            .limit(limit)
            .all()
        )

    return {
        "games": [_serialize_game(g) for g in games],
        "favorite_team_ids": favorite_team_ids,
        "onboarded": bool(favorite_team_ids),
    }


@router.get("/games/{game_id}/fan-recap")
def get_fan_recap(game_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cache_key = f"fan_recap:{user.id}:{game_id}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    existing = db.query(FanRecap).filter_by(user_id=user.id, game_id=game_id).first()
    if existing and existing.content:
        result = {"game_id": game_id, "content": existing.content, "status": "ready"}
        cache_set(cache_key, result)
        return result

    return {"game_id": game_id, "content": None, "status": "not_generated"}


@router.post("/games/{game_id}/fan-recap/generate")
async def generate_fan_recap(game_id: int, background_tasks: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    game = db.query(Game).get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    favorite_team_ids = [ft.team_id for ft in user.favorite_teams]
    if not favorite_team_ids:
        raise HTTPException(status_code=400, detail="No favorite teams set. Complete onboarding first.")

    # Pick the team that's in this game
    game_team_ids = [game.home_team_id, game.away_team_id]
    matching = [tid for tid in favorite_team_ids if tid in game_team_ids]
    fav_team_id = matching[0] if matching else favorite_team_ids[0]

    lock_key = f"{user.id}:{game_id}"
    if _fan_recap_locks.get(lock_key):
        return {"status": "already_generating"}

    _fan_recap_locks[lock_key] = True

    async def _run():
        try:
            content = await fan_perspective_agent(game_id=game_id, user_id=user.id, favorite_team_id=fav_team_id)
            cache_set(f"fan_recap:{user.id}:{game_id}", {"game_id": game_id, "content": content, "status": "ready"})
        finally:
            _fan_recap_locks[lock_key] = False

    background_tasks.add_task(_run)
    return {"status": "generating", "game_id": game_id}
