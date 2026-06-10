from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.espn_public import (
    extract_summary_highlights,
    extract_summary_plays,
    fetch_espn_game_by_id,
    fetch_espn_games,
    fetch_espn_summary_by_id,
)
from db.models import Game, Play, CVClassification
from db.session import get_db
from video.youtube_search import search_highlight_video

router = APIRouter(prefix="/api/games", tags=["games"])


def _serialize_game(g: Game) -> dict:
    return {
        "id": g.id,
        "external_id": g.external_id,
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
    seasons: int = Query(10, ge=1, le=10),
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
    serialized = [_serialize_game(g) for g in games]

    if offset == 0 and len(serialized) < limit and sport:
        espn_games = fetch_espn_games(sport.upper(), date=date, limit=limit, seasons=seasons)
        seen = {g.get("external_id") for g in serialized}
        for espn_game in espn_games:
            if espn_game.get("external_id") not in seen:
                serialized.append(espn_game)
            if len(serialized) >= limit:
                break
        total = max(total, len(serialized))

    return {"total": total, "games": serialized}


@router.get("/{game_id}")
def get_game(game_id: int, db: Session = Depends(get_db)):
    game = db.query(Game).get(game_id)
    if not game:
        resolved = fetch_espn_game_by_id(game_id)
        if resolved:
            return resolved[1]
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
        resolved = fetch_espn_summary_by_id(game_id)
        if resolved:
            sport, summary = resolved
            plays = extract_summary_plays(summary, sport, limit=limit + offset)
            if period:
                plays = [p for p in plays if p["period"] == period]
            if play_type:
                plays = [p for p in plays if p["play_type"] == play_type]
            return {"total": len(plays), "plays": plays[offset:offset + limit]}
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
        resolved_game = fetch_espn_game_by_id(game_id)
        resolved_summary = fetch_espn_summary_by_id(game_id)
        if resolved_game and resolved_summary:
            sport, espn_game = resolved_game
            _, summary = resolved_summary
            try:
                home = (espn_game or {}).get("home_team", {}).get("name") or "home"
                away = (espn_game or {}).get("away_team", {}).get("name") or "away"
                game_date = ((espn_game or {}).get("game_date") or "")[:10]
                video_url = search_highlight_video(home, away, game_date, sport)
                classifications = extract_summary_highlights(summary, sport)
            except Exception:
                video_url = None
                classifications = []
            return {
                "game_id": game_id,
                "video_url": video_url,
                "classifications": classifications,
            }
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
