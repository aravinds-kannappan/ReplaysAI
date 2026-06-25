from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.auth import router as auth_router
from api.broadcast import router as broadcast_router
from api.chat import router as chat_router
from api.dream_team import router as dream_team_router
from api.fantasy import router as fantasy_router
from api.feed import router as feed_router
from api.games import router as games_router
from api.insights import router as insights_router
from api.leaderboards import router as leaderboard_router
from api.news import router as news_router
from api.newsletter import router as newsletter_router
from api.predictions import router as predictions_router
from api.personalization import router as personalization_router
from api.rankings import router as rankings_router
from api.recaps import router as recaps_router
from api.reel_intent import router as reel_intent_router
from api.reels import router as reels_router
from api.waitlist import router as waitlist_router
from config import get_settings


def create_app() -> FastAPI:
    app = FastAPI(title="Replays AI", version="2.0.0")
    settings = get_settings()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(broadcast_router)
    app.include_router(chat_router)
    app.include_router(feed_router)
    app.include_router(games_router)
    app.include_router(newsletter_router)
    app.include_router(recaps_router)
    app.include_router(reel_intent_router)
    app.include_router(reels_router)
    app.include_router(rankings_router)
    app.include_router(predictions_router)
    app.include_router(personalization_router)
    app.include_router(fantasy_router)
    app.include_router(dream_team_router)
    app.include_router(leaderboard_router)
    app.include_router(news_router)
    app.include_router(insights_router)
    app.include_router(waitlist_router)

    @app.get("/health")
    def health():
        return {"status": "ok", "version": "2.0.0", "storage": "espn_public"}

    return app


app = create_app()
