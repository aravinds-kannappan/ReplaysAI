from sqlalchemy import (
    BigInteger, Column, Float, ForeignKey, Index, Integer,
    String, Text, DateTime, func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    abbreviation = Column(String(10))
    sport = Column(String(10))
    conference = Column(String(50))
    division = Column(String(50))

    players = relationship("Player", back_populates="team")
    home_games = relationship("Game", foreign_keys="Game.home_team_id", back_populates="home_team")
    away_games = relationship("Game", foreign_keys="Game.away_team_id", back_populates="away_team")


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    team_id = Column(Integer, ForeignKey("teams.id"))
    position = Column(String(20))
    jersey_number = Column(Integer)
    external_id = Column(String(50), unique=True)

    team = relationship("Team", back_populates="players")
    plays = relationship("Play", back_populates="player")


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True)
    external_id = Column(String(50), unique=True)
    sport = Column(String(10))
    home_team_id = Column(Integer, ForeignKey("teams.id"))
    away_team_id = Column(Integer, ForeignKey("teams.id"))
    game_date = Column(DateTime)
    status = Column(String(20))
    home_score = Column(Integer, default=0)
    away_score = Column(Integer, default=0)
    video_url = Column(Text)
    raw_meta = Column(JSONB)

    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_games")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_games")
    plays = relationship("Play", back_populates="game")
    features = relationship("GameFeature", back_populates="game", uselist=False)
    cv_classifications = relationship("CVClassification", back_populates="game")
    recap = relationship("Recap", back_populates="game", uselist=False)


class Play(Base):
    __tablename__ = "plays"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"))
    period = Column(Integer)
    clock = Column(String(10))
    play_type = Column(String(50))
    description = Column(Text)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    home_score = Column(Integer)
    away_score = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())

    game = relationship("Game", back_populates="plays")
    player = relationship("Player", back_populates="plays")

    __table_args__ = (Index("plays_game_id_idx", "game_id"),)


class GameFeature(Base):
    __tablename__ = "game_features"

    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.id"), unique=True)
    momentum_shifts = Column(JSONB)
    key_moments = Column(JSONB)
    top_performers = Column(JSONB)
    computed_at = Column(DateTime, server_default=func.now())

    game = relationship("Game", back_populates="features")


class CVClassification(Base):
    __tablename__ = "cv_classifications"

    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.id"))
    frame_timestamp = Column(Float)
    play_type = Column(String(100))
    confidence = Column(Float)
    frame_url = Column(Text)
    classified_at = Column(DateTime, server_default=func.now())

    game = relationship("Game", back_populates="cv_classifications")


class Recap(Base):
    __tablename__ = "recaps"

    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.id"), unique=True)
    content = Column(Text)
    model_version = Column(String(50))
    generated_at = Column(DateTime, server_default=func.now())

    game = relationship("Game", back_populates="recap")
