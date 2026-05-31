"""
YouTube Data API v3 search for game highlight videos.
Falls back to constructing a search URL when no API key is available.
"""
import httpx
from typing import Optional
from config import get_settings


YT_SEARCH_BASE = "https://www.googleapis.com/youtube/v3/search"


def search_highlight_video(team1: str, team2: str, game_date: str, sport: str = "NBA") -> Optional[str]:
    """Return the YouTube watch URL for the best highlight video found."""
    settings = get_settings()

    query = f"{team1} vs {team2} {game_date} highlights {sport}"

    if not settings.youtube_api_key:
        # Construct a YouTube search URL the frontend can open
        from urllib.parse import urlencode
        return f"https://www.youtube.com/results?{urlencode({'search_query': query})}"

    try:
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": 5,
            "videoDuration": "medium",
            "key": settings.youtube_api_key,
        }
        r = httpx.get(YT_SEARCH_BASE, params=params, timeout=10)
        r.raise_for_status()
        items = r.json().get("items", [])

        for item in items:
            vid_id = item.get("id", {}).get("videoId")
            if vid_id:
                return f"https://www.youtube.com/watch?v={vid_id}"
    except Exception as e:
        print(f"[YouTube] Search failed: {e}")

    return None
