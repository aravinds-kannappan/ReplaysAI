"""
Fantasy-lite roster endpoints backed by ESPN athletes and client-side saves.
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.espn_public import fetch_espn_athletes
from middleware.clerk_auth import AuthUser, get_current_user

router = APIRouter(prefix="/api/rosters", tags=["fantasy"])


def _current_week_label() -> str:
    now = datetime.now()
    return f"{now.isocalendar()[0]}-W{now.isocalendar()[1]:02d}"


@router.get("")
def list_rosters(_user: AuthUser = Depends(get_current_user)):
    return []


@router.get("/players")
def available_players(sport: Optional[str] = None):
    if not sport:
        return []
    return fetch_espn_athletes(sport.upper(), limit=100)


class RosterBody(BaseModel):
    sport: str
    player_ids: List[int]
    week_label: Optional[str] = None


@router.post("")
def upsert_roster(body: RosterBody, _user: AuthUser = Depends(get_current_user)):
    if len(body.player_ids) > 8:
        raise HTTPException(status_code=400, detail="Max 8 players per roster")
    return {
        "id": body.week_label or _current_week_label(),
        "sport": body.sport.upper(),
        "week_label": body.week_label or _current_week_label(),
        "player_ids": body.player_ids,
        "total_points": 0,
        "locked": False,
        "storage": "client",
    }
