"""
Leaderboard endpoints, backed by the Redis points sorted set (db/store.py).

Ranks are real: they are the running total of points a device has earned from
correctly scored picks. Handles are anonymous (Fan-XXXX unless the fan set a
display name). When no REDIS_URL is configured the leaderboard is empty.
"""
from fastapi import APIRouter, Depends

from middleware.identity import AuthUser, get_current_user
from db import store

router = APIRouter(prefix="/api", tags=["leaderboard"])


@router.get("/leaderboard")
def get_leaderboard(limit: int = 50):
    return store.top_leaders(limit)


@router.get("/leaderboard/me")
def get_my_rank(user: AuthUser = Depends(get_current_user)):
    return store.rank_and_neighbors(user.id)
