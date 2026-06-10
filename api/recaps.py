from fastapi import APIRouter, HTTPException

from api.espn_public import (
    extract_summary_highlights,
    extract_summary_plays,
    fetch_espn_game,
    fetch_espn_game_by_id,
    fetch_espn_game_summary,
)
from cache.redis_client import cache_get, cache_set

router = APIRouter(prefix="/api/games", tags=["recaps"])


def _public_game_recap(game_id: int, sport: str, event_id: str) -> dict:
    game = fetch_espn_game(sport, event_id)
    summary = fetch_espn_game_summary(sport, event_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    plays = extract_summary_plays(summary, sport, limit=200)
    highlights = extract_summary_highlights(summary, sport)
    away = game["away_team"]["name"] or "Away"
    home = game["home_team"]["name"] or "Home"
    away_score = game["away_score"]
    home_score = game["home_score"]
    date_label = (game.get("game_date") or "")[:10] or "recent game"

    if away_score is not None and home_score is not None:
        winner = home if home_score > away_score else away
        result_line = f"{away} {away_score}, {home} {home_score}"
        lead = f"{winner} shaped the game in a matchup pulled from ESPN's public package."
    else:
        result_line = f"{away} at {home}"
        lead = f"{away} and {home} are on the board from ESPN's schedule feed."

    key_plays = [play for play in plays if play["play_type"] != "other"][:6]
    if key_plays:
        moments = "\n".join(f"- Q{play['period']} {play['clock']}: {play['description']}" for play in key_plays)
    else:
        moments = "- ESPN has not published detailed play-by-play for this matchup yet."

    content = f"""# {away} vs. {home} - {date_label}
**{result_line}**

## Game Read
{lead} ReplaysAI is using public ESPN scoreboard and summary endpoints for this card, so it updates as ESPN publishes score, play, and box score data.

## Moments To Watch
{moments}

## Reel Context
{len(highlights)} highlight-style moments are available from play labels.
"""
    return {
        "game_id": game_id,
        "content": content,
        "status": "espn_generated",
        "cv_classifications": len(highlights),
    }


@router.get("/{game_id}/recap")
def get_recap(game_id: int):
    cache_key = f"recap:{game_id}"
    cached = cache_get(cache_key)
    if cached:
        return cached
    resolved = fetch_espn_game_by_id(game_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="Game not found")
    sport, _ = resolved
    result = _public_game_recap(game_id, sport, str(game_id))
    cache_set(cache_key, result)
    return result


@router.post("/{game_id}/generate")
async def trigger_generation(game_id: int):
    return get_recap(game_id)
