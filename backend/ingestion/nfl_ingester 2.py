"""
Ingests NFL play-by-play data from ESPN's unofficial API into PostgreSQL.
"""
import time
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from backend.db.models import Game, Play, Player, Team
from backend.db.session import get_session_factory

SPORT = "NFL"
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
REQUEST_DELAY = 0.3

NFL_TEAMS = [
    ("Arizona Cardinals", "ARI", "NFC", "West"),
    ("Atlanta Falcons", "ATL", "NFC", "South"),
    ("Baltimore Ravens", "BAL", "AFC", "North"),
    ("Buffalo Bills", "BUF", "AFC", "East"),
    ("Carolina Panthers", "CAR", "NFC", "South"),
    ("Chicago Bears", "CHI", "NFC", "North"),
    ("Cincinnati Bengals", "CIN", "AFC", "North"),
    ("Cleveland Browns", "CLE", "AFC", "North"),
    ("Dallas Cowboys", "DAL", "NFC", "East"),
    ("Denver Broncos", "DEN", "AFC", "West"),
    ("Detroit Lions", "DET", "NFC", "North"),
    ("Green Bay Packers", "GB", "NFC", "North"),
    ("Houston Texans", "HOU", "AFC", "South"),
    ("Indianapolis Colts", "IND", "AFC", "South"),
    ("Jacksonville Jaguars", "JAX", "AFC", "South"),
    ("Kansas City Chiefs", "KC", "AFC", "West"),
    ("Las Vegas Raiders", "LV", "AFC", "West"),
    ("Los Angeles Chargers", "LAC", "AFC", "West"),
    ("Los Angeles Rams", "LAR", "NFC", "West"),
    ("Miami Dolphins", "MIA", "AFC", "East"),
    ("Minnesota Vikings", "MIN", "NFC", "North"),
    ("New England Patriots", "NE", "AFC", "East"),
    ("New Orleans Saints", "NO", "NFC", "South"),
    ("New York Giants", "NYG", "NFC", "East"),
    ("New York Jets", "NYJ", "AFC", "East"),
    ("Philadelphia Eagles", "PHI", "NFC", "East"),
    ("Pittsburgh Steelers", "PIT", "AFC", "North"),
    ("San Francisco 49ers", "SF", "NFC", "West"),
    ("Seattle Seahawks", "SEA", "NFC", "West"),
    ("Tampa Bay Buccaneers", "TB", "NFC", "South"),
    ("Tennessee Titans", "TEN", "AFC", "South"),
    ("Washington Commanders", "WAS", "NFC", "East"),
]


def _upsert_nfl_teams(db: Session) -> dict[str, int]:
    abbr_to_id: dict[str, int] = {}
    for name, abbr, conf, div in NFL_TEAMS:
        existing = db.query(Team).filter_by(abbreviation=abbr, sport=SPORT).first()
        if not existing:
            team = Team(name=name, abbreviation=abbr, sport=SPORT, conference=conf, division=div)
            db.add(team)
            db.flush()
            abbr_to_id[abbr] = team.id
        else:
            abbr_to_id[abbr] = existing.id
    db.commit()
    return abbr_to_id


def _fetch_scoreboard(week: Optional[int] = None) -> list[dict]:
    params = {"limit": 100}
    if week:
        params["week"] = week
    try:
        r = httpx.get(f"{ESPN_BASE}/scoreboard", params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data.get("events", [])
    except Exception as e:
        print(f"[NFL] Scoreboard fetch failed: {e}")
        return []


def _fetch_game_summary(event_id: str) -> Optional[dict]:
    try:
        time.sleep(REQUEST_DELAY)
        r = httpx.get(f"{ESPN_BASE}/summary", params={"event": event_id}, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[NFL] Summary fetch failed for {event_id}: {e}")
        return None


def _classify_nfl_play(description: str) -> str:
    desc = description.lower()
    if "pass" in desc and "complete" in desc:
        return "pass_complete"
    if "pass" in desc and "incomplete" in desc:
        return "pass_incomplete"
    if "rush" in desc or "run" in desc:
        return "rush"
    if "sack" in desc:
        return "sack"
    if "touchdown" in desc or "td" in desc:
        return "touchdown"
    if "interception" in desc:
        return "interception"
    if "fumble" in desc:
        return "fumble"
    if "field goal" in desc:
        return "field_goal"
    if "punt" in desc:
        return "punt"
    if "kickoff" in desc:
        return "kickoff"
    if "penalty" in desc:
        return "penalty"
    return "other"


def run_ingestion(weeks: int = 3) -> None:
    SessionLocal = get_session_factory()
    db: Session = SessionLocal()

    print("[NFL] Upserting teams...")
    abbr_to_id = _upsert_nfl_teams(db)

    print(f"[NFL] Fetching recent scoreboard...")
    events = _fetch_scoreboard()

    total_plays = 0

    for event in events:
        event_id = event.get("id", "")
        if not event_id:
            continue

        existing = db.query(Game).filter_by(external_id=event_id, sport=SPORT).first()
        status_type = event.get("status", {}).get("type", {}).get("name", "")
        is_final = status_type == "STATUS_FINAL"

        if existing and existing.status == "final":
            continue

        competitions = event.get("competitions", [{}])
        comp = competitions[0] if competitions else {}
        competitors = comp.get("competitors", [])

        home_team_data = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away_team_data = next((c for c in competitors if c.get("homeAway") == "away"), None)

        if not home_team_data or not away_team_data:
            continue

        home_abbr = home_team_data.get("team", {}).get("abbreviation", "")
        away_abbr = away_team_data.get("team", {}).get("abbreviation", "")

        home_id = abbr_to_id.get(home_abbr)
        away_id = abbr_to_id.get(away_abbr)

        if not home_id or not away_id:
            continue

        home_score = int(home_team_data.get("score", 0) or 0)
        away_score = int(away_team_data.get("score", 0) or 0)

        date_str = event.get("date", "")
        try:
            game_date = datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            game_date = datetime.now()

        if existing:
            existing.status = "final" if is_final else "live"
            existing.home_score = home_score
            existing.away_score = away_score
            db.commit()
            game_db_id = existing.id
        else:
            game = Game(
                external_id=event_id,
                sport=SPORT,
                home_team_id=home_id,
                away_team_id=away_id,
                game_date=game_date,
                status="final" if is_final else "scheduled",
                home_score=home_score,
                away_score=away_score,
                raw_meta={"season": "2025"},
            )
            db.add(game)
            db.flush()
            db.commit()
            game_db_id = game.id

        if is_final and db.query(Play).filter_by(game_id=game_db_id).count() == 0:
            print(f"  Fetching plays for {home_abbr} vs {away_abbr} ({event_id})...")
            summary = _fetch_game_summary(event_id)
            if summary:
                drives = summary.get("drives", {}).get("previous", [])
                plays_to_add = []
                period = 1
                for drive in drives:
                    for play in drive.get("plays", []):
                        desc = play.get("text", "")
                        period = play.get("period", {}).get("number", period)
                        clock = play.get("clock", {}).get("displayValue", "")
                        plays_to_add.append(Play(
                            game_id=game_db_id,
                            period=period,
                            clock=clock,
                            play_type=_classify_nfl_play(desc),
                            description=desc[:500],
                            player_id=None,
                            home_score=None,
                            away_score=None,
                        ))
                if plays_to_add:
                    db.bulk_save_objects(plays_to_add)
                    db.commit()
                    total_plays += len(plays_to_add)
                    print(f"    {len(plays_to_add)} plays ingested")

    print(f"[NFL] Done. {len(events)} events scanned, {total_plays} plays ingested.")
    db.close()


if __name__ == "__main__":
    run_ingestion()
