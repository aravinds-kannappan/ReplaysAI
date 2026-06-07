from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional

from cache.redis_client import cache_get, cache_set
from db.models import Game, Team
from db.session import get_db

router = APIRouter(prefix="/api", tags=["rankings"])

STANDINGS_TTL = 300  # 5 minutes


def _compute_standings(db: Session, sport: str) -> list[dict]:
    teams = db.query(Team).filter_by(sport=sport.upper()).all()
    records: dict[int, dict] = {}

    for t in teams:
        records[t.id] = {
            "team_id": t.id,
            "name": t.name,
            "abbreviation": t.abbreviation,
            "conference": t.conference,
            "division": t.division,
            "wins": 0,
            "losses": 0,
            "win_pct": 0.0,
        }

    games = db.query(Game).filter(Game.sport == sport.upper(), Game.status == "final").all()
    for g in games:
        if g.home_score is None or g.away_score is None:
            continue
        if g.home_score > g.away_score:
            if g.home_team_id in records:
                records[g.home_team_id]["wins"] += 1
            if g.away_team_id in records:
                records[g.away_team_id]["losses"] += 1
        else:
            if g.away_team_id in records:
                records[g.away_team_id]["wins"] += 1
            if g.home_team_id in records:
                records[g.home_team_id]["losses"] += 1

    for r in records.values():
        total = r["wins"] + r["losses"]
        r["win_pct"] = round(r["wins"] / total, 3) if total > 0 else 0.0

    return sorted(records.values(), key=lambda x: (-x["wins"], -x["win_pct"]))


@router.get("/rankings")
def get_rankings(sport: Optional[str] = Query(None), db: Session = Depends(get_db)):
    sports = [sport.upper()] if sport else ["NBA", "NFL"]
    result = {}

    for s in sports:
        cache_key = f"rankings:{s}"
        cached = cache_get(cache_key)
        if cached:
            result[s] = cached
            continue

        standings = _compute_standings(db, s)
        cache_set(cache_key, standings, ttl=STANDINGS_TTL)
        result[s] = standings

    return result


@router.get("/teams")
def get_teams(sport: Optional[str] = Query(None), db: Session = Depends(get_db)):
    if db.query(Team).count() == 0:
        from ingestion.nba_ingester import _upsert_nba_teams
        from ingestion.nfl_ingester import _upsert_nfl_teams

        _upsert_nba_teams(db)
        _upsert_nfl_teams(db)

    q = db.query(Team)
    if sport:
        q = q.filter(Team.sport == sport.upper())
    teams = q.order_by(Team.sport, Team.name).all()
    return [
        {
            "id": team.id,
            "name": team.name,
            "abbreviation": team.abbreviation,
            "sport": team.sport,
            "conference": team.conference,
            "division": team.division,
        }
        for team in teams
    ]


@router.get("/players/{player_id}")
def get_player(player_id: int, db: Session = Depends(get_db)):
    from db.models import Player, Play
    player = db.query(Player).get(player_id)
    if not player:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Player not found")

    play_counts = {}
    plays = db.query(Play).filter_by(player_id=player_id).all()
    for p in plays:
        play_counts[p.play_type] = play_counts.get(p.play_type, 0) + 1

    return {
        "id": player.id,
        "name": player.name,
        "position": player.position,
        "jersey_number": player.jersey_number,
        "team": {"id": player.team_id, "name": player.team.name if player.team else None},
        "play_stats": play_counts,
        "total_plays": len(plays),
    }
