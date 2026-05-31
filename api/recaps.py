import asyncio
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from agents.orchestrator import generate_game_recap
from cache.redis_client import cache_get, cache_set
from db.models import Game, Recap
from db.session import get_db

router = APIRouter(prefix="/api/games", tags=["recaps"])

_generation_locks: dict[int, bool] = {}


@router.get("/{game_id}/recap")
def get_recap(game_id: int, db: Session = Depends(get_db)):
    cache_key = f"recap:{game_id}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    game = db.query(Game).get(game_id)
    if not game:
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
