from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.espn_public import (
    extract_summary_highlights,
    extract_summary_plays,
    fetch_espn_game_by_id,
    fetch_espn_games,
    fetch_espn_summary_by_id,
)
from video.youtube_search import search_highlight_video

router = APIRouter(prefix="/api/games", tags=["games"])


def _matches_status(game: dict, status: Optional[str]) -> bool:
    return not status or game.get("status") == status


def _matches_date(game: dict, date: Optional[str]) -> bool:
    if not date:
        return True
    game_date = game.get("game_date")
    if not game_date:
        return False
    try:
        return datetime.fromisoformat(game_date).date().isoformat() == date
    except ValueError:
        return game_date.startswith(date)


@router.get("")
def list_games(
    sport: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    seasons: int = Query(10, ge=1, le=10),
):
    sports = [sport.upper()] if sport else ["NBA", "NFL"]
    rows: list[dict] = []
    for sport_key in sports:
        rows.extend(fetch_espn_games(sport_key, date=date, limit=limit + offset, seasons=seasons))

    rows = [game for game in rows if _matches_status(game, status) and _matches_date(game, date)]
    rows = sorted(rows, key=lambda game: game.get("game_date") or "", reverse=True)
    paged = rows[offset:offset + limit]
    return {"total": len(rows), "games": paged}


@router.get("/{game_id}")
def get_game(game_id: int):
    resolved = fetch_espn_game_by_id(game_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="Game not found")
    return resolved[1]


@router.get("/{game_id}/plays")
def get_plays(
    game_id: int,
    period: Optional[int] = Query(None),
    play_type: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    resolved = fetch_espn_summary_by_id(game_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="Game not found")
    sport, summary = resolved
    plays = extract_summary_plays(summary, sport, limit=limit + offset + 100)
    if period:
        plays = [play for play in plays if play["period"] == period]
    if play_type:
        plays = [play for play in plays if play["play_type"] == play_type]
    return {"total": len(plays), "plays": plays[offset:offset + limit]}


@router.get("/{game_id}/highlights")
def get_highlights(game_id: int):
    resolved_game = fetch_espn_game_by_id(game_id)
    resolved_summary = fetch_espn_summary_by_id(game_id)
    if not resolved_game or not resolved_summary:
        raise HTTPException(status_code=404, detail="Game not found")
    sport, game = resolved_game
    _, summary = resolved_summary
    home = game["home_team"].get("name") or "home"
    away = game["away_team"].get("name") or "away"
    game_date = (game.get("game_date") or "")[:10]
    return {
        "game_id": game_id,
        "video_url": search_highlight_video(home, away, game_date, sport),
        "classifications": extract_summary_highlights(summary, sport),
    }
