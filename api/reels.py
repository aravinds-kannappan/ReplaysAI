from fastapi import APIRouter, HTTPException

from api.espn_public import (
    extract_summary_highlights,
    extract_summary_plays,
    fetch_espn_game_by_id,
    fetch_espn_summary_by_id,
)
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
    highlight_types = {highlight["play_type"] for highlight in highlights}
    segments = []
    for index, play in enumerate(plays):
        play_type = play.get("play_type") or "other"
        if play_type == "other" and play_type not in highlight_types:
            continue
        segments.append({
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
    return sorted(segments, key=lambda item: (-item["weight"], item["timestamp"]))[:40]


def _cuts_from_segments(segments: list[dict]) -> list[dict]:
    cuts = []
    for length in CUT_LENGTHS:
        running = 0
        selected = []
        for segment in segments:
            if running + segment["duration"] > length and selected:
                continue
            selected.append({key: value for key, value in segment.items() if key != "weight"})
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
def get_reel_cuts(game_id: int):
    resolved_game = fetch_espn_game_by_id(game_id)
    resolved_summary = fetch_espn_summary_by_id(game_id)
    if not resolved_game or not resolved_summary:
        raise HTTPException(status_code=404, detail="Game not found")

    sport, game_data = resolved_game
    _, summary = resolved_summary
    plays = extract_summary_plays(summary, sport, limit=500)
    highlights = extract_summary_highlights(summary, sport)
    segments = _build_segments(plays, highlights)
    return {
        "game_id": game_id,
        "video_url": _video_url_for_game(game_data),
        "cuts": _cuts_from_segments(segments),
        "rendering": {
            "mp4_available": False,
            "reason": "Vercel serverless returns timestamped reel manifests; MP4 rendering needs a background ffmpeg worker plus object storage.",
        },
    }
