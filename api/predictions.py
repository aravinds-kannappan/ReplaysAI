"""
Prediction CRUD: users pick game winners before kickoff/tipoff.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.espn_public import fetch_espn_game_by_id, fetch_espn_games
from db.models import Game, Prediction, Team, User
from db.session import get_db
from middleware.clerk_auth import get_current_user

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
    predictions = db.query(Prediction).filter_by(user_id=user.id).all()
    predicted_game_ids = {p.game_id for p in predictions}
    predicted_external_ids = {p.game.external_id for p in predictions if p.game and p.game.external_id}
    rows = [
        {
            "id": g.id,
            "external_id": g.external_id,
            "sport": g.sport,
            "game_date": g.game_date.isoformat() if g.game_date else None,
            "home_team": {"id": g.home_team_id, "name": g.home_team.name if g.home_team else None},
            "away_team": {"id": g.away_team_id, "name": g.away_team.name if g.away_team else None},
            "already_predicted": g.id in predicted_game_ids,
        }
        for g in games
    ]
    seen = {row.get("external_id") for row in rows if row.get("external_id")}
    for sport in ("NBA", "NFL"):
        for game in fetch_espn_games(sport, limit=20):
            if game["status"] != "scheduled" or game.get("external_id") in seen:
                continue
            rows.append({
                "id": game["id"],
                "external_id": game.get("external_id"),
                "sport": game["sport"],
                "game_date": game.get("game_date"),
                "home_team": game["home_team"],
                "away_team": game["away_team"],
                "already_predicted": game.get("external_id") in predicted_external_ids,
            })
            seen.add(game.get("external_id"))
            if len(rows) >= 40:
                return rows
    return rows


class PredictionBody(BaseModel):
    game_id: int
    predicted_winner_team_id: int
    predicted_score_diff: Optional[int] = None


def _parse_game_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _upsert_team(db: Session, team_data: dict, sport: str) -> Team:
    team = (
        db.query(Team)
        .filter(Team.sport == sport, Team.abbreviation == team_data.get("abbreviation"))
        .first()
    )
    if not team:
        team = Team(
            name=team_data.get("name"),
            abbreviation=team_data.get("abbreviation"),
            sport=sport,
            conference="",
            division="",
        )
        db.add(team)
    else:
        team.name = team_data.get("name") or team.name
        team.abbreviation = team_data.get("abbreviation") or team.abbreviation
        team.sport = sport
    return team


def _materialize_public_game(db: Session, espn_event_id: int) -> Game | None:
    event_id = str(espn_event_id)
    resolved = fetch_espn_game_by_id(event_id)
    if not resolved:
        return None
    sport, game_data = resolved
    existing = db.query(Game).filter_by(external_id=event_id, sport=sport).first()
    if existing:
        return existing

    home = _upsert_team(db, game_data["home_team"], sport)
    away = _upsert_team(db, game_data["away_team"], sport)
    db.flush()

    game = Game(
        external_id=event_id,
        sport=sport,
        home_team_id=home.id,
        away_team_id=away.id,
        game_date=_parse_game_date(game_data.get("game_date")),
        status=game_data["status"],
        home_score=game_data.get("home_score"),
        away_score=game_data.get("away_score"),
        video_url=game_data.get("video_url"),
        raw_meta={"source": "espn_public"},
    )
    db.add(game)
    db.flush()
    return game


@router.post("")
def create_prediction(body: PredictionBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    game = db.query(Game).get(body.game_id)
    if not game:
        game = _materialize_public_game(db, body.game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.status == "final":
        raise HTTPException(status_code=400, detail="Game already finished")
    predicted_winner_team_id = body.predicted_winner_team_id
    if game.external_id == str(body.game_id):
        resolved = fetch_espn_game_by_id(body.game_id)
        if resolved:
            _, game_data = resolved
            if body.predicted_winner_team_id == game_data["home_team"]["id"]:
                predicted_winner_team_id = game.home_team_id
            elif body.predicted_winner_team_id == game_data["away_team"]["id"]:
                predicted_winner_team_id = game.away_team_id

    existing = db.query(Prediction).filter_by(user_id=user.id, game_id=game.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Already predicted this game")

    pred = Prediction(
        user_id=user.id,
        game_id=game.id,
        predicted_winner_team_id=predicted_winner_team_id,
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
