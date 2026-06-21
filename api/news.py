"""News headlines, filtered to the teams and players a fan follows.

There is no general/random sports news: if a fan has selected nothing, the feed
is empty. Otherwise only articles mentioning their teams or players are returned.
"""
from typing import Optional

from fastapi import APIRouter, Query

from api.espn_public import fetch_espn_news

router = APIRouter(prefix="/api", tags=["news"])


@router.get("/news")
def get_news(sport: Optional[str] = Query(None), keywords: str = Query(""), limit: int = 12):
    kws = [k.strip().lower() for k in keywords.split(",") if k.strip()]
    if not kws:
        # Nothing followed → no personalized news (never general sports news).
        return []
    articles = fetch_espn_news(sport, limit=50)
    matched = [
        a for a in articles
        if any(k in f"{a.get('headline','')} {a.get('description','')}".lower() for k in kws)
    ]
    return matched[:limit]
