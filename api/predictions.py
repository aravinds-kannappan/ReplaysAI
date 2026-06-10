"""
Prediction endpoints without database storage.
The frontend stores user picks locally; schedules come from ESPN.
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.espn_public import fetch_espn_game_by_id, fetch_espn_games
from middleware.clerk_auth import AuthUser, get_current_user

router = APIRouter(prefix="/api/predictions", tags=["predictions"])


@router.get("")
def list_predictions(_status: Optional[str] = None, _user: AuthUser = Depends(get_current_user)):
    return []


@router.get("/upcoming")
def upcoming_games(_user: AuthUser = Depends(get_current_user)):
    rows = []
    for sport in ("NBA", "NFL"):
        for game in fetch_espn_games(sport, limit=40, seasons=1):
            if game["status"] != "scheduled":
                continue
            rows.append({
                "id": game["id"],
                "external_id": game.get("external_id"),
                "sport": game["sport"],
                "game_date": game.get("game_date"),
                "home_team": game["home_team"],
                "away_team": game["away_team"],
                "already_predicted": False,
            })
    return sorted(rows, key=lambda row: row.get("game_date") or "")[:40]


class PredictionBody(BaseModel):
    game_id: int
    predicted_winner_team_id: int
    predicted_score_diff: Optional[int] = None


@router.post("")
def create_prediction(body: PredictionBody, user: AuthUser = Depends(get_current_user)):
    resolved = fetch_espn_game_by_id(body.game_id)
    game = resolved[1] if resolved else None
    return {
        "id": body.game_id,
        "game_id": body.game_id,
        "predicted_winner_team_id": body.predicted_winner_team_id,
        "predicted_score_diff": body.predicted_score_diff,
        "is_correct": None,
        "points_earned": 0,
        "game": game,
        "storage": "client",
    }
