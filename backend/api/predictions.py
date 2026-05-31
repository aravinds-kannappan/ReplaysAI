"""
Prediction CRUD: users pick game winners before kickoff/tipoff.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.models import Game, Prediction, User
from backend.db.session import get_db
from backend.middleware.clerk_auth import get_current_user

router = APIRouter(prefix="/api/predictions", tags=["predictions"])


def _serialize_prediction(p: Prediction) -> dict:
    return {
        "id": p.id,
        "game_id": p.game_id,
        "predicted_winner_team_id": p.predicted_winner_team_id,
        "predicted_winner_name": p.predicted_winner.name if p.predicted_winner else None,
        "predicted_score_diff": p.predicted_score_diff,
        "is_correct": p.is_correct,
        "points_earned": p.points_earned,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "resolved_at": p.resolved_at.isoformat() if p.resolved_at else None,
        "game": {
            "sport": p.game.sport,
            "status": p.game.status,
            "game_date": p.game.game_date.isoformat() if p.game and p.game.game_date else None,
            "home_team": p.game.home_team.name if p.game and p.game.home_team else None,
            "away_team": p.game.away_team.name if p.game and p.game.away_team else None,
            "home_score": p.game.home_score if p.game else None,
            "away_score": p.game.away_score if p.game else None,
        } if p.game else None,
    }


@router.get("")
def list_predictions(status: Optional[str] = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Prediction).filter_by(user_id=user.id)
    if status == "pending":
        q = q.filter(Prediction.resolved_at.is_(None))
    elif status == "resolved":
        q = q.filter(Prediction.resolved_at.isnot(None))
    preds = q.order_by(Prediction.created_at.desc()).all()
    return [_serialize_prediction(p) for p in preds]


@router.get("/upcoming")
def upcoming_games(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Games that haven't started yet and user hasn't predicted."""
    games = db.query(Game).filter(Game.status == "scheduled").order_by(Game.game_date).limit(20).all()
    predicted_game_ids = {p.game_id for p in db.query(Prediction).filter_by(user_id=user.id).all()}
    return [
        {
            "id": g.id,
            "sport": g.sport,
            "game_date": g.game_date.isoformat() if g.game_date else None,
            "home_team": {"id": g.home_team_id, "name": g.home_team.name if g.home_team else None},
            "away_team": {"id": g.away_team_id, "name": g.away_team.name if g.away_team else None},
            "already_predicted": g.id in predicted_game_ids,
        }
        for g in games
    ]


class PredictionBody(BaseModel):
    game_id: int
    predicted_winner_team_id: int
    predicted_score_diff: Optional[int] = None


@router.post("")
def create_prediction(body: PredictionBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    game = db.query(Game).get(body.game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.status == "final":
        raise HTTPException(status_code=400, detail="Game already finished")

    existing = db.query(Prediction).filter_by(user_id=user.id, game_id=body.game_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Already predicted this game")

    pred = Prediction(
        user_id=user.id,
        game_id=body.game_id,
        predicted_winner_team_id=body.predicted_winner_team_id,
        predicted_score_diff=body.predicted_score_diff,
    )
    db.add(pred)

    # Points for first prediction of week
    if user.streaks:
        user.streaks.total_predictions += 1
        if user.points:
            user.points.engagement_points += 10
            user.points.total_points += 10

    db.commit()
    db.refresh(pred)
    return _serialize_prediction(pred)
