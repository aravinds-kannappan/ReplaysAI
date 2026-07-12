"""
Prediction (pick'em) endpoints.

Picks are stored per anonymous device in the Redis store (db/store.py) and
scored for real: when a picked game finishes, the pick resolves on the next read
and points flow to the leaderboard. When no REDIS_URL is configured the store
degrades to no-op and picks simply do not persist.
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.espn_public import fetch_espn_game_by_id, fetch_espn_games
from middleware.identity import AuthUser, get_current_user, get_optional_user
from db import store

router = APIRouter(prefix="/api/predictions", tags=["predictions"])


def _winner_team_id(game: dict) -> Optional[int]:
    """The winning team id once a game is played. Both scores present means the
    game is final (ESPN sometimes mislabels the status string, so the scoreline
    is the source of truth). None while a game is unplayed or tied."""
    hs, as_ = game.get("home_score"), game.get("away_score")
    if hs is None or as_ is None or hs == as_:
        return None
    return game["home_team"]["id"] if hs > as_ else game["away_team"]["id"]


def _resolve_finished(device_id: str, picks: dict[int, dict]) -> None:
    """Score any picks whose game has finished, oldest first so streaks count
    in chronological order."""
    pending = [p for p in picks.values() if not p.get("resolved")]
    for pick in sorted(pending, key=lambda x: x.get("game_date") or ""):
        resolved = fetch_espn_game_by_id(pick["game_id"])
        if not resolved:
            continue
        winner = _winner_team_id(resolved[1])
        if winner is None:
            continue
        store.mark_resolved(device_id, pick["game_id"], pick["predicted_winner_team_id"] == winner)


@router.get("")
def list_predictions(_status: Optional[str] = None, user: AuthUser = Depends(get_current_user)):
    picks = store.get_pick_map(user.id)
    if picks:
        _resolve_finished(user.id, picks)
        picks = store.get_pick_map(user.id)
    return [
        {
            "id": p["game_id"],
            "game_id": p["game_id"],
            "predicted_winner_team_id": p["predicted_winner_team_id"],
            "is_correct": p.get("is_correct"),
            "resolved_at": p.get("resolved_at"),
            "points_earned": p.get("points_earned", 0),
        }
        for p in picks.values()
    ]


@router.get("/upcoming")
def upcoming_games(user: Optional[AuthUser] = Depends(get_optional_user)):
    picked = set(store.get_pick_map(user.id).keys()) if user else set()
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
                "already_predicted": game["id"] in picked,
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
    sport = resolved[0] if resolved else None
    game_date = (game or {}).get("game_date")
    pick = store.save_pick(user.id, body.game_id, body.predicted_winner_team_id, sport, game_date)
    return {
        "id": body.game_id,
        "game_id": body.game_id,
        "predicted_winner_team_id": body.predicted_winner_team_id,
        "predicted_score_diff": body.predicted_score_diff,
        "is_correct": pick.get("is_correct"),
        "points_earned": pick.get("points_earned", 0),
        "game": game,
        "storage": "store" if store.store_enabled() else "ephemeral",
    }
