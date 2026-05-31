from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.auth import router as auth_router
from api.fantasy import router as fantasy_router
from api.feed import router as feed_router
from api.games import router as games_router
from api.leaderboards import router as leaderboard_router
from api.predictions import router as predictions_router
from api.rankings import router as rankings_router
from api.recaps import router as recaps_router
from db.models import Badge, Base
from db.session import get_engine, get_session_factory

app = FastAPI(title="Replays AI", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(feed_router)
app.include_router(games_router)
app.include_router(recaps_router)
app.include_router(rankings_router)
app.include_router(predictions_router)
app.include_router(fantasy_router)
app.include_router(leaderboard_router)


BADGE_SEEDS = [
    {"slug": "week1",    "name": "First Pick",    "description": "Made your first prediction",    "icon": "🎯", "threshold": 1},
    {"slug": "oracle",   "name": "Oracle",        "description": "10 correct predictions",        "icon": "🔮", "threshold": 10},
    {"slug": "loyal",    "name": "Loyal Fan",     "description": "7-day login streak",            "icon": "🔥", "threshold": 7},
    {"slug": "superfan", "name": "Superfan",      "description": "30-day login streak",           "icon": "🏆", "threshold": 30},
    {"slug": "analyst",  "name": "Analyst",       "description": "Generated 10 recaps",           "icon": "📊", "threshold": 10},
    {"slug": "clutch",   "name": "Clutch",        "description": "Predicted a game within 5 pts", "icon": "⏱️",  "threshold": 1},
]


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=get_engine())
    db = get_session_factory()()
    try:
        for seed in BADGE_SEEDS:
            if not db.query(Badge).filter_by(slug=seed["slug"]).first():
                db.add(Badge(**seed))
        db.commit()
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}
