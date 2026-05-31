from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.games import router as games_router
from backend.api.recaps import router as recaps_router
from backend.api.rankings import router as rankings_router
from backend.db.models import Base
from backend.db.session import get_engine

app = FastAPI(title="Replays AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(games_router)
app.include_router(recaps_router)
app.include_router(rankings_router)


@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=get_engine())


@app.get("/health")
def health():
    return {"status": "ok"}
