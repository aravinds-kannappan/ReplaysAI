from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.espn_public import (
    extract_summary_highlights,
    extract_summary_plays,
    fetch_espn_game_by_id,
    fetch_espn_summary_by_id,
)
from db.models import CVClassification, Game, Play
from db.session import get_db
from video.youtube_search import search_highlight_video

router = APIRouter(prefix="/api/games", tags=["reels"])

CUT_LENGTHS = [120, 300, 600]


def _video_url_for_game(game: dict) -> str | None:
    home = game["home_team"].get("name") or "home"
    away = game["away_team"].get("name") or "away"
    game_date = (game.get("game_date") or "")[:10]
    return search_highlight_video(home, away, game_date, game.get("sport") or "NBA")


def _segment_weight(play_type: str) -> int:
    weights = {
        "touchdown": 10,
        "dunk": 9,
        "three_pointer": 8,
        "interception": 8,
        "sack": 7,
        "block": 7,
        "steal": 7,
        "field_goal": 6,
        "turnover": 6,
        "assist": 5,
        "shot": 4,
    }
    return weights.get(play_type, 1)


def _build_segments(plays: list[dict], highlights: list[dict]) -> list[dict]:
    by_index = []
    highlight_types = {h["play_type"] for h in highlights}
    for index, play in enumerate(plays):
        play_type = play.get("play_type") or "other"
        if play_type == "other" and play_type not in highlight_types:
            continue
        by_index.append({
            "timestamp": float(index * 35),
            "duration": 18,
            "period": play.get("period"),
            "clock": play.get("clock"),
            "play_type": play_type,
            "description": play.get("description"),
            "score": {
                "away": play.get("away_score"),
                "home": play.get("home_score"),
            },
            "weight": _segment_weight(play_type),
        })

    ranked = sorted(by_index, key=lambda item: (-item["weight"], item["timestamp"]))
    return ranked[:40]


def _cuts_from_segments(segments: list[dict]) -> list[dict]:
    cuts = []
    for length in CUT_LENGTHS:
        running = 0
        selected = []
        for segment in segments:
            if running + segment["duration"] > length and selected:
                continue
            selected.append({k: v for k, v in segment.items() if k != "weight"})
            running += segment["duration"]
            if running >= length:
                break
        cuts.append({
            "duration_seconds": length,
            "label": f"{length // 60} min cut",
            "segments": selected,
            "estimated_seconds": running,
            "status": "ready" if selected else "no_segments",
        })
    return cuts


@router.get("/{game_id}/reels")
def get_reel_cuts(game_id: int, db: Session = Depends(get_db)):
    game = db.query(Game).get(game_id)
    if game:
        game_data = {
            "id": game.id,
            "sport": game.sport,
            "game_date": game.game_date.isoformat() if game.game_date else None,
            "home_team": {"name": game.home_team.name if game.home_team else None},
            "away_team": {"name": game.away_team.name if game.away_team else None},
        }
        db_plays = db.query(Play).filter_by(game_id=game_id).order_by(Play.id).limit(500).all()
        plays = [
            {
                "period": play.period,
                "clock": play.clock,
                "play_type": play.play_type,
                "description": play.description,
                "home_score": play.home_score,
                "away_score": play.away_score,
            }
            for play in db_plays
        ]
        highlights = [
            {"timestamp": row.frame_timestamp, "play_type": row.play_type, "confidence": row.confidence}
            for row in db.query(CVClassification).filter_by(game_id=game_id).all()
        ]
        video_url = game.video_url or _video_url_for_game(game_data)
    else:
        resolved_game = fetch_espn_game_by_id(game_id)
        resolved_summary = fetch_espn_summary_by_id(game_id)
        if not resolved_game or not resolved_summary:
            raise HTTPException(status_code=404, detail="Game not found")
        sport, game_data = resolved_game
        _, summary = resolved_summary
        plays = extract_summary_plays(summary, sport, limit=500)
        highlights = extract_summary_highlights(summary, sport)
        video_url = _video_url_for_game(game_data)

    segments = _build_segments(plays, highlights)
    return {
        "game_id": game_id,
        "video_url": video_url,
        "cuts": _cuts_from_segments(segments),
        "rendering": {
            "mp4_available": False,
            "reason": "Vercel serverless returns timestamped reel manifests; MP4 rendering should run in a background worker with ffmpeg storage.",
        },
    }
