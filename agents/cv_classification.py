"""
Agent 2: CV Play Classification
Downloads YouTube highlight video, extracts frames, sends batches to Claude Vision.
Classifies each frame as a play type and stores results.
"""
import asyncio
import json
from typing import Optional

import anthropic

from config import get_settings
from db.models import CVClassification, Game
from db.session import get_session_factory
from video.frame_extractor import get_video_frames_for_game
from video.youtube_search import search_highlight_video

PLAY_TYPES = ["dunk", "three_pointer", "block", "steal", "turnover",
              "free_throw", "assist", "touchdown", "interception", "field_goal",
              "sack", "crowd_reaction", "replay", "other"]

BATCH_SIZE = 5


async def _classify_frame_batch(
    client: anthropic.Anthropic,
    model: str,
    frames: list[tuple[float, str]],
) -> list[dict]:
    """Send a batch of frames to Claude Vision and return classifications."""
    content = []
    for _, b64 in frames:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
        })

    content.append({
        "type": "text",
        "text": (
            f"You are analyzing frames from a sports highlight video. "
            f"For each of the {len(frames)} images above (in order), classify what play or scene is shown. "
            f"Valid play types: {', '.join(PLAY_TYPES)}. "
            f"Return a JSON array of objects with keys 'index' (0-based), 'play_type', and 'confidence' (0.0–1.0). "
            f"Only return the JSON array, no explanation."
        ),
    })

    loop = asyncio.get_event_loop()
    try:
        response = await loop.run_in_executor(
            None,
            lambda: client.messages.create(
                model=model,
                max_tokens=512,
                messages=[{"role": "user", "content": content}],
            ),
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        print(f"[CV] Batch classification failed: {e}")
        return [{"index": i, "play_type": "other", "confidence": 0.0} for i in range(len(frames))]


async def cv_classification_agent(game_id: int) -> list[dict]:
    SessionLocal = get_session_factory()
    db = SessionLocal()
    results = []

    try:
        game = db.query(Game).get(game_id)
        if not game:
            return []

        existing = db.query(CVClassification).filter_by(game_id=game_id).count()
        if existing > 0:
            rows = db.query(CVClassification).filter_by(game_id=game_id).all()
            return [{"timestamp": r.frame_timestamp, "play_type": r.play_type, "confidence": r.confidence} for r in rows]

        home_name = game.home_team.name if game.home_team else "Home"
        away_name = game.away_team.name if game.away_team else "Away"
        game_date = game.game_date.strftime("%Y-%m-%d") if game.game_date else ""

        video_url = game.video_url
        if not video_url:
            video_url = search_highlight_video(home_name, away_name, game_date, game.sport or "NBA")
            if video_url:
                game.video_url = video_url
                db.commit()

        if not video_url or "youtube.com/results" in video_url:
            print(f"[CV] No direct video for game {game_id}, skipping CV inference")
            return []

        print(f"[CV] Extracting frames from: {video_url}")
        frames = get_video_frames_for_game(video_url, interval_seconds=3.0)

        if not frames:
            print(f"[CV] No frames extracted for game {game_id}")
            return []

        print(f"[CV] Got {len(frames)} frames, classifying in batches of {BATCH_SIZE}...")
        settings = get_settings()
        if not settings.anthropic_api_key:
            print(f"[CV] No ANTHROPIC_API_KEY configured, skipping vision inference")
            return []
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        classifications_to_save = []
        for batch_start in range(0, len(frames), BATCH_SIZE):
            batch = frames[batch_start: batch_start + BATCH_SIZE]
            batch_results = await _classify_frame_batch(client, settings.anthropic_model, batch)

            for item in batch_results:
                idx = item.get("index", 0)
                if batch_start + idx < len(frames):
                    timestamp = frames[batch_start + idx][0]
                    play_type = item.get("play_type", "other")
                    confidence = float(item.get("confidence", 0.5))
                    classifications_to_save.append(CVClassification(
                        game_id=game_id,
                        frame_timestamp=timestamp,
                        play_type=play_type,
                        confidence=confidence,
                        frame_url=None,
                    ))
                    results.append({"timestamp": timestamp, "play_type": play_type, "confidence": confidence})

        if classifications_to_save:
            db.bulk_save_objects(classifications_to_save)
            db.commit()

        print(f"[CV] Saved {len(classifications_to_save)} classifications for game {game_id}")
        return results

    finally:
        db.close()
