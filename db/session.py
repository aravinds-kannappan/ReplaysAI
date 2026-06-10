import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        database_url = os.environ.get("INGESTION_DATABASE_URL")
        if not database_url:
            raise RuntimeError("INGESTION_DATABASE_URL is required only for ingestion scripts or optional DB-backed jobs.")
        _engine = create_engine(
            database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal


def get_db() -> Session:
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
