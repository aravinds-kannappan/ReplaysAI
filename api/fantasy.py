"""
Fantasy-lite: solo weekly roster builder.
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.models import Play, Player, Team, User, UserRoster
from db.session import get_db
from middleware.clerk_auth import get_current_user

router = APIRouter(prefix="/api/rosters", tags=["fantasy"])


def _current_week_label() -> str:
    now = datetime.now()
    return f"{now.isocalendar()[0]}-W{now.isocalendar()[1]:02d}"


def _player_impact_score(player_id: int, db: Session) -> float:
    plays = db.query(Play).filter_by(player_id=player_id).all()
    score = sum(
        {"dunk": 5, "three_pointer": 4, "block": 3, "steal": 3, "assist": 2,
         "touchdown": 6, "pass_complete": 1, "sack": 3, "interception": 4}.get(p.play_type, 0)
        for p in plays
    )
    return round(score / max(1, len({p.game_id for p in plays})), 1)


@router.get("")
def list_rosters(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rosters = db.query(UserRoster).filter_by(user_id=user.id).order_by(UserRoster.created_at.desc()).all()
    return [{"id": r.id, "sport": r.sport, "week_label": r.week_label, "player_ids": r.player_ids, "total_points": r.total_points, "locked": r.locked} for r in rosters]


@router.get("/players")
def available_players(sport: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Player).join(Team, Player.team_id == Team.id, isouter=True)
    if sport:
        q = q.filter(Team.sport == sport.upper())
    players = q.limit(100).all()
    result = []
    for p in players:
        score = _player_impact_score(p.id, db)
        result.append({
            "id": p.id,
            "name": p.name,
            "position": p.position,
            "team": p.team.abbreviation if p.team else None,
            "sport": p.team.sport if p.team else None,
            "impact_score": score,
        })
    return sorted(result, key=lambda x: -x["impact_score"])


class RosterBody(BaseModel):
    sport: str
    player_ids: List[int]
    week_label: Optional[str] = None


@router.post("")
def upsert_roster(body: RosterBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if len(body.player_ids) > 8:
        raise HTTPException(status_code=400, detail="Max 8 players per roster")

    week = body.week_label or _current_week_label()
    existing = db.query(UserRoster).filter_by(user_id=user.id, sport=body.sport.upper(), week_label=week).first()

    if existing:
        if existing.locked:
            raise HTTPException(status_code=400, detail="Roster is locked for this week")
        existing.player_ids = body.player_ids
        db.commit()
        db.refresh(existing)
        return {"id": existing.id, "week_label": week, "player_ids": existing.player_ids}
    else:
        roster = UserRoster(user_id=user.id, sport=body.sport.upper(), week_label=week, player_ids=body.player_ids)
        db.add(roster)
        db.commit()
        db.refresh(roster)
        return {"id": roster.id, "week_label": week, "player_ids": roster.player_ids}
