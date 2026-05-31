"""
Prediction Scorer: runs after a game goes final.
Scores pending predictions, awards points, triggers badge checks.
"""
from datetime import datetime

from sqlalchemy.orm import Session

from backend.db.models import Badge, Game, Notification, Prediction, User, UserBadge, UserPoints, UserStreak
from backend.db.session import get_session_factory


def _maybe_award_badge(user_id: int, slug: str, db: Session) -> None:
    badge = db.query(Badge).filter_by(slug=slug).first()
    if not badge:
        return
    already = db.query(UserBadge).filter_by(user_id=user_id, badge_id=badge.id).first()
    if not already:
        db.add(UserBadge(user_id=user_id, badge_id=badge.id))


def score_game_predictions(game_id: int) -> int:
    """Score all pending predictions for a game. Returns number of predictions scored."""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    scored = 0

    try:
        game = db.query(Game).get(game_id)
        if not game or game.status != "final":
            return 0

        actual_winner_id = game.home_team_id if (game.home_score or 0) > (game.away_score or 0) else game.away_team_id
        score_diff = abs((game.home_score or 0) - (game.away_score or 0))

        pending = db.query(Prediction).filter_by(game_id=game_id, resolved_at=None).all()

        for pred in pending:
            is_correct = pred.predicted_winner_team_id == actual_winner_id
            points = 0

            if is_correct:
                points = 100
                if pred.predicted_score_diff is not None and abs(pred.predicted_score_diff - score_diff) <= 5:
                    points = 150  # "clutch" bonus

            pred.is_correct = is_correct
            pred.points_earned = points
            pred.resolved_at = datetime.utcnow()

            # Update user points + streaks
            user_pts = db.query(UserPoints).filter_by(user_id=pred.user_id).first()
            streak = db.query(UserStreak).filter_by(user_id=pred.user_id).first()

            if user_pts:
                user_pts.prediction_points += points
                user_pts.total_points += points
                user_pts.updated_at = datetime.utcnow()

            if streak:
                if is_correct:
                    streak.correct_predictions += 1
                    streak.prediction_streak += 1
                else:
                    streak.prediction_streak = 0

                # Badge checks
                if streak.correct_predictions == 1:
                    _maybe_award_badge(pred.user_id, "week1", db)
                if streak.correct_predictions >= 10:
                    _maybe_award_badge(pred.user_id, "oracle", db)
                if is_correct and points == 150:
                    _maybe_award_badge(pred.user_id, "clutch", db)

            # Create notification
            result_text = "✅ Correct" if is_correct else "❌ Incorrect"
            pts_text = f"+{points} pts" if points > 0 else "No points"
            db.add(Notification(
                user_id=pred.user_id,
                type="prediction_result",
                title=f"Prediction result: {result_text}",
                body=f"{game.away_team.name if game.away_team else 'Away'} @ {game.home_team.name if game.home_team else 'Home'} is final. Your pick was {result_text}. {pts_text}",
                game_id=game_id,
            ))
            scored += 1

        db.commit()
        return scored

    finally:
        db.close()
