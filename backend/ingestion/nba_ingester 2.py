"""
Ingests NBA play-by-play data via ESPN's unofficial API (primary)
with nba_api as fallback for detailed stats.
"""
import time
from datetime import datetime, timedelta
from typing import Optional

import httpx
from nba_api.stats.static import teams as nba_teams_static
from sqlalchemy.orm import Session

from backend.db.models import Game, Play, Player, Team
from backend.db.session import get_session_factory

SPORT = "NBA"
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
REQUEST_DELAY = 0.4


def _upsert_nba_teams(db: Session) -> dict[str, int]:
    all_teams = nba_teams_static.get_teams()
    abbr_to_id: dict[str, int] = {}
    for t in all_teams:
        existing = db.query(Team).filter_by(abbreviation=t["abbreviation"], sport=SPORT).first()
        if not existing:
            team = Team(
                name=t["full_name"],
                abbreviation=t["abbreviation"],
                sport=SPORT,
                conference="",
                division="",
            )
            db.add(team)
            db.flush()
            abbr_to_id[t["abbreviation"]] = team.id
        else:
            abbr_to_id[t["abbreviation"]] = existing.id
    db.commit()
    return abbr_to_id


def _fetch_espn_scoreboard(date_str: Optional[str] = None) -> list[dict]:
    """Fetch NBA scoreboard from ESPN. date_str format: YYYYMMDD"""
    params: dict = {"limit": 100}
    if date_str:
        params["dates"] = date_str
    try:
        r = httpx.get(f"{ESPN_BASE}/scoreboard", params=params, timeout=15)
        r.raise_for_status()
        return r.json().get("events", [])
    except Exception as e:
        print(f"[NBA] ESPN scoreboard error: {e}")
        return []


def _fetch_espn_game_summary(event_id: str) -> Optional[dict]:
    try:
        time.sleep(REQUEST_DELAY)
        r = httpx.get(f"{ESPN_BASE}/summary", params={"event": event_id}, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[NBA] ESPN summary error for {event_id}: {e}")
        return None


def _classify_play_type(description: str) -> str:
    desc = description.lower()
    if "3pt" in desc or "3-pt" in desc or "three point" in desc:
        return "three_pointer"
    if "dunk" in desc:
        return "dunk"
    if "block" in desc:
        return "block"
    if "steal" in desc:
        return "steal"
    if "free throw" in desc:
        return "free_throw"
    if "turnover" in desc:
        return "turnover"
    if "assist" in desc:
        return "assist"
    if "rebound" in desc:
        return "rebound"
    if "foul" in desc:
        return "foul"
    if "jump ball" in desc:
        return "jump_ball"
    return "other"


def _ingest_plays_from_summary(db: Session, game_db_id: int, summary: dict) -> int:
    """Extract plays from ESPN summary's plays array."""
    plays_raw = summary.get("plays", [])
    if not plays_raw:
        # Try inside drives
        drives = summary.get("drives", {})
        if isinstance(drives, dict):
            for drive_list in drives.values():
                if isinstance(drive_list, list):
                    for drive in drive_list:
                        for p in drive.get("plays", []):
                            plays_raw.append(p)

    plays_to_add = []
    for play in plays_raw:
        desc = play.get("text", "") or play.get("description", "")
        period_data = play.get("period", {})
        period = period_data.get("number", 1) if isinstance(period_data, dict) else 1
        clock = play.get("clock", {}).get("displayValue", "") if isinstance(play.get("clock"), dict) else str(play.get("clock", ""))

        home_score = None
        away_score = None
        score_str = play.get("homeScore") or play.get("awayScore")
        if play.get("homeScore") is not None:
            try:
                home_score = int(play["homeScore"])
                away_score = int(play["awayScore"])
            except Exception:
                pass

        plays_to_add.append(Play(
            game_id=game_db_id,
            period=period,
            clock=str(clock),
            play_type=_classify_play_type(desc),
            description=str(desc)[:500],
            player_id=None,
            home_score=home_score,
            away_score=away_score,
        ))

    if plays_to_add:
        db.bulk_save_objects(plays_to_add)
        db.commit()
    return len(plays_to_add)


def run_ingestion(days_back: int = 14) -> None:
    SessionLocal = get_session_factory()
    db: Session = SessionLocal()

    print("[NBA] Upserting teams...")
    abbr_to_id = _upsert_nba_teams(db)

    total_plays = 0
    total_games = 0

    # Fetch games for each of the last days_back days
    for day_offset in range(0, days_back):
        date = datetime.now() - timedelta(days=day_offset)
        date_str = date.strftime("%Y%m%d")
        events = _fetch_espn_scoreboard(date_str)

        for event in events:
            event_id = event.get("id", "")
            if not event_id:
                continue

            status_type = event.get("status", {}).get("type", {}).get("name", "")
            is_final = status_type == "STATUS_FINAL"

            existing = db.query(Game).filter_by(external_id=event_id, sport=SPORT).first()
            if existing and existing.status == "final":
                continue

            competitions = event.get("competitions", [{}])
            comp = competitions[0] if competitions else {}
            competitors = comp.get("competitors", [])

            home_data = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away_data = next((c for c in competitors if c.get("homeAway") == "away"), None)

            if not home_data or not away_data:
                continue

            home_abbr = home_data.get("team", {}).get("abbreviation", "")
            away_abbr = away_data.get("team", {}).get("abbreviation", "")

            # ESPN uses different abbreviations for some NBA teams
            abbr_map = {"GS": "GSW", "SA": "SAS", "NO": "NOP", "NY": "NYK", "OKC": "OKC", "WSH": "WAS", "UTAH": "UTA", "PHX": "PHX"}
            home_abbr = abbr_map.get(home_abbr, home_abbr)
            away_abbr = abbr_map.get(away_abbr, away_abbr)

            home_id = abbr_to_id.get(home_abbr)
            away_id = abbr_to_id.get(away_abbr)

            if not home_id or not away_id:
                # Try to find by name
                home_name = home_data.get("team", {}).get("displayName", "")
                away_name = away_data.get("team", {}).get("displayName", "")
                home_team = db.query(Team).filter(Team.name.ilike(f"%{home_name.split()[-1]}%"), Team.sport == SPORT).first()
                away_team = db.query(Team).filter(Team.name.ilike(f"%{away_name.split()[-1]}%"), Team.sport == SPORT).first()
                home_id = home_team.id if home_team else None
                away_id = away_team.id if away_team else None

            if not home_id or not away_id:
                continue

            home_score = int(home_data.get("score", 0) or 0)
            away_score = int(away_data.get("score", 0) or 0)

            date_iso = event.get("date", "")
            try:
                game_date = datetime.fromisoformat(date_iso.replace("Z", "+00:00")).replace(tzinfo=None)
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
                    raw_meta={"season": "2024-25"},
                )
                db.add(game)
                db.flush()
                db.commit()
                game_db_id = game.id
                total_games += 1

            if is_final and db.query(Play).filter_by(game_id=game_db_id).count() == 0:
                home_name = home_data.get("team", {}).get("displayName", home_abbr)
                away_name = away_data.get("team", {}).get("displayName", away_abbr)
                print(f"  Fetching plays: {away_name} @ {home_name} ({event_id})...")
                summary = _fetch_espn_game_summary(event_id)
                if summary:
                    n = _ingest_plays_from_summary(db, game_db_id, summary)
                    total_plays += n
                    print(f"    {n} plays ingested")

    print(f"[NBA] Done. {total_games} new games, {total_plays} total plays ingested.")
    db.close()


if __name__ == "__main__":
    run_ingestion()
