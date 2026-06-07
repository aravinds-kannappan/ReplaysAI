"""
Fantasy-lite: solo weekly roster builder.
"""
import hashlib
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import Play, Player, PlayerGameStat, Team, User, UserRoster
from db.session import get_db
from middleware.clerk_auth import get_current_user

router = APIRouter(prefix="/api/rosters", tags=["fantasy"])


def _current_week_label() -> str:
    now = datetime.now()
    return f"{now.isocalendar()[0]}-W{now.isocalendar()[1]:02d}"


def _player_impact_score(player_id: int, db: Session) -> float:
    stat_rows = db.query(PlayerGameStat).filter_by(player_id=player_id).all()
    if stat_rows:
        total = sum(
            (row.points or 0)
            + (row.assists or 0) * 1.5
            + (row.rebounds or 0) * 1.2
            + (row.blocks or 0) * 3
            + (row.steals or 0) * 3
            - (row.turnovers or 0)
            for row in stat_rows
        )
        return round(total / max(1, len(stat_rows)), 1)

    plays = db.query(Play).filter_by(player_id=player_id).all()
    play_score = sum(
        {
            "dunk": 5,
            "three_pointer": 4,
            "block": 3,
            "steal": 3,
            "assist": 2,
            "touchdown": 6,
            "pass_complete": 1,
            "sack": 3,
            "interception": 4,
        }.get(p.play_type, 0)
        for p in plays
    )
    return round(play_score / max(1, len({p.game_id for p in plays})), 1)


def _materialize_players_from_boxscores(db: Session, sport: Optional[str]) -> None:
    """Create Player rows for historical box score names that were ingested before players existed."""
    q = (
        db.query(
            PlayerGameStat.player_name,
            PlayerGameStat.team_id,
            func.count(PlayerGameStat.id).label("games_played"),
        )
        .join(Team, PlayerGameStat.team_id == Team.id, isouter=True)
        .filter(PlayerGameStat.player_id.is_(None), PlayerGameStat.player_name.isnot(None))
    )
    if sport:
        q = q.filter(Team.sport == sport.upper())

    rows = q.group_by(PlayerGameStat.player_name, PlayerGameStat.team_id).limit(300).all()
    changed = False

    for player_name, team_id, _games_played in rows:
        if not player_name:
            continue
        player = (
            db.query(Player)
            .filter(Player.name == player_name, Player.team_id == team_id)
            .first()
        )
        if not player:
            external_key = hashlib.sha1(f"{team_id or 'na'}:{player_name}".encode("utf-8")).hexdigest()[:24]
            player = Player(
                name=player_name,
                team_id=team_id,
                position=None,
                external_id=f"box:{external_key}",
            )
            db.add(player)
            db.flush()

        db.query(PlayerGameStat).filter_by(player_name=player_name, team_id=team_id).update(
            {PlayerGameStat.player_id: player.id},
            synchronize_session=False,
        )
        changed = True

    if changed:
        db.commit()


@router.get("")
def list_rosters(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rosters = db.query(UserRoster).filter_by(user_id=user.id).order_by(UserRoster.created_at.desc()).all()
    return [{"id": r.id, "sport": r.sport, "week_label": r.week_label, "player_ids": r.player_ids, "total_points": r.total_points, "locked": r.locked} for r in rosters]


@router.get("/players")
def available_players(sport: Optional[str] = None, db: Session = Depends(get_db)):
    _materialize_players_from_boxscores(db, sport)

    q = db.query(Player).join(Team, Player.team_id == Team.id, isouter=True)
    if sport:
        q = q.filter(Team.sport == sport.upper())
    players = q.limit(150).all()
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
