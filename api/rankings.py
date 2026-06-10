from typing import Optional

from fastapi import APIRouter, Query

from cache.redis_client import cache_get, cache_set
from api.espn_public import fetch_espn_games, fetch_espn_teams

router = APIRouter(prefix="/api", tags=["rankings"])

STANDINGS_TTL = 300


@router.get("/rankings")
def get_rankings(sport: Optional[str] = Query(None)):
    sports = [sport.upper()] if sport else ["NBA", "NFL"]
    result = {}
    for sport_key in sports:
        cache_key = f"rankings:espn:{sport_key}"
        cached = cache_get(cache_key)
        if cached:
            result[sport_key] = cached
            continue

        teams = {team["abbreviation"]: {**team, "wins": 0, "losses": 0} for team in fetch_espn_teams(sport_key)}
        for game in fetch_espn_games(sport_key, limit=100, seasons=1):
            if game.get("status") != "final":
                continue
            home = game.get("home_team", {}).get("abbreviation")
            away = game.get("away_team", {}).get("abbreviation")
            home_score = game.get("home_score")
            away_score = game.get("away_score")
            if home not in teams or away not in teams or home_score is None or away_score is None:
                continue
            winner, loser = (home, away) if home_score > away_score else (away, home)
            teams[winner]["wins"] += 1
            teams[loser]["losses"] += 1

        standings = []
        for team in teams.values():
            total = team["wins"] + team["losses"]
            standings.append({
                "team_id": team["id"],
                "name": team["name"],
                "abbreviation": team["abbreviation"],
                "conference": team.get("conference") or "",
                "division": team.get("division") or "",
                "wins": team["wins"],
                "losses": team["losses"],
                "win_pct": round(team["wins"] / total, 3) if total else 0,
            })
        standings = sorted(standings, key=lambda row: (-row["wins"], row["name"]))
        cache_set(cache_key, standings, ttl=STANDINGS_TTL)
        result[sport_key] = standings
    return result


@router.get("/teams")
def get_teams(sport: Optional[str] = Query(None)):
    sports = [sport.upper()] if sport else ["NBA", "NFL"]
    teams = []
    for sport_key in sports:
        teams.extend(fetch_espn_teams(sport_key))
    return teams


@router.get("/players/{player_id}")
def get_player(player_id: int):
    from fastapi import HTTPException

    raise HTTPException(status_code=404, detail=f"Player {player_id} is not available from the ESPN team feed")
