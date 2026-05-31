from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.models import Game, Play, CVClassification
from db.session import get_db

router = APIRouter(prefix="/api/games", tags=["games"])


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


@router.get("")
def list_games(
    sport: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    q = db.query(Game)
    if sport:
        q = q.filter(Game.sport == sport.upper())
    if status:
        q = q.filter(Game.status == status)
    if date:
        try:
            d = datetime.strptime(date, "%Y-%m-%d")
            q = q.filter(Game.game_date >= d, Game.game_date < datetime(d.year, d.month, d.day, 23, 59, 59))
        except ValueError:
            pass
    q = q.order_by(Game.game_date.desc())
    total = q.count()
    games = q.offset(offset).limit(limit).all()
    return {"total": total, "games": [_serialize_game(g) for g in games]}


@router.get("/{game_id}")
def get_game(game_id: int, db: Session = Depends(get_db)):
    game = db.query(Game).get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return _serialize_game(game)


@router.get("/{game_id}/plays")
def get_plays(
    game_id: int,
    period: Optional[int] = Query(None),
    play_type: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    game = db.query(Game).get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    q = db.query(Play).filter_by(game_id=game_id)
    if period:
        q = q.filter(Play.period == period)
    if play_type:
        q = q.filter(Play.play_type == play_type)
    q = q.order_by(Play.id)
    total = q.count()
    plays = q.offset(offset).limit(limit).all()
    return {
        "total": total,
        "plays": [
            {
                "id": p.id,
                "period": p.period,
                "clock": p.clock,
                "play_type": p.play_type,
                "description": p.description,
                "home_score": p.home_score,
                "away_score": p.away_score,
                "player": p.player.name if p.player else None,
            }
            for p in plays
        ],
    }


@router.get("/{game_id}/highlights")
def get_highlights(game_id: int, db: Session = Depends(get_db)):
    game = db.query(Game).get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    rows = db.query(CVClassification).filter_by(game_id=game_id).order_by(CVClassification.frame_timestamp).all()
    return {
        "game_id": game_id,
        "video_url": game.video_url,
        "classifications": [
            {"timestamp": r.frame_timestamp, "play_type": r.play_type, "confidence": r.confidence}
            for r in rows
        ],
    }
