from sqlalchemy import (
    BigInteger, Boolean, Column, Date, Float, ForeignKey, Index, Integer,
    String, Text, DateTime, UniqueConstraint, func
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


# ─── User / Auth models ───────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    clerk_id = Column(String(100), unique=True, nullable=False)
    username = Column(String(50), unique=True)
    display_name = Column(String(100))
    email = Column(String(200))
    avatar_url = Column(Text)
    bio = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    favorite_teams = relationship("UserFavoriteTeam", back_populates="user", cascade="all, delete-orphan")
    followed_players = relationship("UserFollowedPlayer", back_populates="user", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="user")
    rosters = relationship("UserRoster", back_populates="user")
    points = relationship("UserPoints", back_populates="user", uselist=False)
    streaks = relationship("UserStreak", back_populates="user", uselist=False)
    badges = relationship("UserBadge", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    fan_recaps = relationship("FanRecap", back_populates="user")


class UserFavoriteTeam(Base):
    __tablename__ = "user_favorite_teams"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)

    user = relationship("User", back_populates="favorite_teams")
    team = relationship("Team")


class UserFollowedPlayer(Base):
    __tablename__ = "user_followed_players"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    player_id = Column(Integer, ForeignKey("players.id", ondelete="CASCADE"), primary_key=True)

    user = relationship("User", back_populates="followed_players")
    player = relationship("Player")


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    game_id = Column(Integer, ForeignKey("games.id"))
    predicted_winner_team_id = Column(Integer, ForeignKey("teams.id"))
    predicted_score_diff = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    resolved_at = Column(DateTime)
    is_correct = Column(Boolean)
    points_earned = Column(Integer, default=0)

    user = relationship("User", back_populates="predictions")
    game = relationship("Game")
    predicted_winner = relationship("Team")

    __table_args__ = (UniqueConstraint("user_id", "game_id"),)


class UserRoster(Base):
    __tablename__ = "user_rosters"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    sport = Column(String(10))
    week_label = Column(String(20))
    player_ids = Column(JSONB)
    total_points = Column(Float, default=0)
    locked = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="rosters")

    __table_args__ = (UniqueConstraint("user_id", "sport", "week_label"),)


class UserPoints(Base):
    __tablename__ = "user_points"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    total_points = Column(Integer, default=0)
    prediction_points = Column(Integer, default=0)
    streak_bonus_points = Column(Integer, default=0)
    engagement_points = Column(Integer, default=0)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="points")


class UserStreak(Base):
    __tablename__ = "user_streaks"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    login_streak = Column(Integer, default=0)
    longest_login_streak = Column(Integer, default=0)
    last_login_date = Column(Date)
    prediction_streak = Column(Integer, default=0)
    total_predictions = Column(Integer, default=0)
    correct_predictions = Column(Integer, default=0)

    user = relationship("User", back_populates="streaks")


class Badge(Base):
    __tablename__ = "badges"

    id = Column(Integer, primary_key=True)
    slug = Column(String(50), unique=True)
    name = Column(String(100))
    description = Column(Text)
    icon = Column(String(10))
    threshold = Column(Integer)

    user_badges = relationship("UserBadge", back_populates="badge")


class UserBadge(Base):
    __tablename__ = "user_badges"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    badge_id = Column(Integer, ForeignKey("badges.id"), primary_key=True)
    earned_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="badges")
    badge = relationship("Badge", back_populates="user_badges")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(String(50))
    title = Column(String(200))
    body = Column(Text)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=True)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="notifications")
    game = relationship("Game")


class FanRecap(Base):
    __tablename__ = "fan_recaps"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    game_id = Column(Integer, ForeignKey("games.id"))
    favorite_team_id = Column(Integer, ForeignKey("teams.id"))
    content = Column(Text)
    generated_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="fan_recaps")
    game = relationship("Game")
    favorite_team = relationship("Team")

    __table_args__ = (UniqueConstraint("user_id", "game_id"),)
