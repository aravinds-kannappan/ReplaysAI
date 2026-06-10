"""
Personalized feed and fan-perspective recap endpoints.
"""
from fastapi import APIRouter, HTTPException, Query

from api.espn_public import fetch_espn_games, fetch_espn_game_by_id
from cache.redis_client import cache_get, cache_set

router = APIRouter(prefix="/api", tags=["feed"])


def _parse_favorite_keys(raw: str | None) -> set[tuple[str, str]]:
    keys = set()
    for item in (raw or "").split(","):
        if ":" not in item:
            continue
        sport, abbreviation = item.split(":", 1)
        if sport and abbreviation:
            keys.add((sport.upper(), abbreviation.upper()))
    return keys


def _game_team_keys(game: dict) -> set[tuple[str, str]]:
    sport = game.get("sport", "").upper()
    return {
        (sport, (game.get("home_team") or {}).get("abbreviation", "").upper()),
        (sport, (game.get("away_team") or {}).get("abbreviation", "").upper()),
    }


@router.get("/feed")
def get_personalized_feed(
    limit: int = 20,
    favorite_teams: str | None = Query(None),
):
    favorite_keys = _parse_favorite_keys(favorite_teams)
    rows = []
    # When filtering by favorites, keep everything each season window returns
    # (the scoreboard call fetches up to 100 games regardless), otherwise a
    # per-window truncation leaves only finals games and favorite teams that
    # missed deep playoff runs never show up.
    fetch_limit = 1000 if favorite_keys else limit
    for sport in ("NBA", "NFL"):
        for game in fetch_espn_games(sport, limit=fetch_limit, seasons=10):
            if favorite_keys and not (favorite_keys & _game_team_keys(game)):
                continue
            rows.append(game)
    rows = sorted(rows, key=lambda game: game.get("game_date") or "", reverse=True)[:limit]
    return {
        "games": rows,
        "favorite_team_ids": [],
        "favorite_team_keys": [f"{sport}:{abbr}" for sport, abbr in sorted(favorite_keys)],
        "onboarded": bool(favorite_keys),
    }


@router.get("/games/{game_id}/fan-recap")
def get_fan_recap(game_id: int):
    cached = cache_get(f"fan_recap:{game_id}")
    if cached:
        return cached
    return {"game_id": game_id, "content": None, "status": "not_generated"}


@router.post("/games/{game_id}/fan-recap/generate")
async def generate_fan_recap(game_id: int):
    resolved = fetch_espn_game_by_id(game_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="Game not found")
    _, game = resolved
    away = game["away_team"].get("name") or "Away"
    home = game["home_team"].get("name") or "Home"
    content = (
        f"# {away} at {home}\n\n"
        "This fan view is generated from the public ESPN game package. "
        "Pick one of these teams in onboarding and the dashboard will prioritize their games immediately."
    )
    result = {"game_id": game_id, "content": content, "status": "ready"}
    cache_set(f"fan_recap:{game_id}", result)
    return result
