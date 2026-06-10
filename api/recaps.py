import asyncio
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from agents.orchestrator import generate_game_recap
from api.espn_public import (
    extract_summary_highlights,
    extract_summary_plays,
    fetch_espn_game,
    fetch_espn_game_summary,
    fetch_espn_game_by_id,
)
from cache.redis_client import cache_get, cache_set
from db.models import Game, Recap
from db.session import get_db

router = APIRouter(prefix="/api/games", tags=["recaps"])

_generation_locks: dict[int, bool] = {}


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

    scored = away_score is not None and home_score is not None
    if scored:
        winner = home if home_score > away_score else away
        result_line = f"{away} {away_score}, {home} {home_score}"
        lead = f"{winner} set the tone in a {sport} matchup pulled from ESPN's live game package."
    else:
        result_line = f"{away} at {home}"
        lead = f"{away} and {home} are on the board from ESPN's public schedule feed."

    key_plays = [p for p in plays if p["play_type"] != "other"][:6]
    if key_plays:
        moments = "\n".join(f"- Q{p['period']} {p['clock']}: {p['description']}" for p in key_plays)
    else:
        moments = "- ESPN has not published detailed play-by-play for this matchup yet."

    content = f"""# {away} vs. {home} - {date_label}
**{result_line}**

## Game Read
{lead} ReplaysAI is using the public ESPN scoreboard and summary endpoints for this card, so the recap updates as ESPN publishes more scoring, play-by-play, and box score data.

## Moments To Watch
{moments}

## Reel Context
{len(highlights)} highlight-style moments are available from play labels. When a direct highlight video is found, the vision pipeline can attach frame classifications to this same game view.
"""
    return {
        "game_id": game_id,
        "content": content,
        "status": "espn_generated",
        "cv_classifications": len(highlights),
    }


@router.get("/{game_id}/recap")
def get_recap(game_id: int, db: Session = Depends(get_db)):
    cache_key = f"recap:{game_id}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    game = db.query(Game).get(game_id)
    if not game:
        resolved = fetch_espn_game_by_id(game_id)
        if resolved:
            sport, _ = resolved
            event_id = str(game_id)
            result = _public_game_recap(game_id, sport, event_id)
            cache_set(cache_key, result)
            return result
        raise HTTPException(status_code=404, detail="Game not found")

    recap = db.query(Recap).filter_by(game_id=game_id).first()
    if recap and recap.content:
        result = {"game_id": game_id, "content": recap.content, "generated_at": recap.generated_at.isoformat()}
        cache_set(cache_key, result)
        return result

    return {"game_id": game_id, "content": None, "status": "not_generated"}


@router.post("/{game_id}/generate")
async def trigger_generation(game_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    game = db.query(Game).get(game_id)
    if not game:
        resolved = fetch_espn_game_by_id(game_id)
        if resolved:
            sport, _ = resolved
            event_id = str(game_id)
            result = _public_game_recap(game_id, sport, event_id)
            cache_set(f"recap:{game_id}", result)
            return {"status": "generated", "game_id": game_id}
        raise HTTPException(status_code=404, detail="Game not found")
    if game.status not in ("final", "live"):
        raise HTTPException(status_code=400, detail="Can only generate recaps for completed or live games")

    if _generation_locks.get(game_id):
        return {"status": "already_generating", "game_id": game_id}

    _generation_locks[game_id] = True

    async def _run():
        try:
            result = await generate_game_recap(game_id)
            cache_set(f"recap:{game_id}", {
                "game_id": game_id,
                "content": result["recap"],
                "cv_classifications": result["cv_classifications"],
            })
        finally:
            _generation_locks[game_id] = False

    background_tasks.add_task(_run)
    return {"status": "generating", "game_id": game_id}
