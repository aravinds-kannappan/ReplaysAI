"""
NFL data ingestion via ESPN unofficial API.

Two modes:
  • backfill_historical_nfl()  – pulls all games for N past seasons (idempotent)
  • run_live_refresh()         – updates current week's games only

Run directly:
  python -m backend.ingestion.nfl_ingester --mode backfill --seasons 5
  python -m backend.ingestion.nfl_ingester --mode live
"""
import argparse
import time
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy.orm import Session
from tqdm import tqdm

from backend.db.models import Game, Play, Player, PlayerGameStat, Team
from backend.db.session import get_session_factory

SPORT = "NFL"
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"

REQUEST_DELAY = 0.4

# Season types: 1=preseason, 2=regular, 3=postseason
SEASON_TYPES = [2, 3]  # regular + playoffs

# Max weeks per season type
MAX_REGULAR_WEEKS = 18
MAX_PLAYOFF_WEEKS = 4

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


# ─── helpers ─────────────────────────────────────────────────────────────────

def _get(url: str, params: dict | None = None, retries: int = 3) -> dict | None:
    for attempt in range(retries):
        try:
            r = httpx.get(url, params=params or {}, timeout=20)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
        except Exception as e:
            if attempt == retries - 1:
                print(f"  ✗ GET {url} failed: {e}")
    return None


def _safe_int(v) -> Optional[int]:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


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


def _resolve_team(abbr: str, name: str, db: Session, abbr_to_id: dict[str, int]) -> Optional[int]:
    if abbr in abbr_to_id:
        return abbr_to_id[abbr]
    last = name.split()[-1] if name else ""
    t = db.query(Team).filter(Team.name.ilike(f"%{last}%"), Team.sport == SPORT).first()
    if t:
        abbr_to_id[abbr] = t.id
        return t.id
    return None


def _classify_nfl_play(desc: str) -> str:
    d = desc.lower()
    if "touchdown" in d or " td " in d:  return "touchdown"
    if "pass" in d and "complete" in d:  return "pass_complete"
    if "pass" in d and "incomplete" in d: return "pass_incomplete"
    if "sack" in d:                       return "sack"
    if "interception" in d:               return "interception"
    if "fumble" in d:                     return "fumble"
    if "rush" in d or "up the middle" in d or "left end" in d or "right end" in d: return "rush"
    if "field goal" in d:                 return "field_goal"
    if "extra point" in d:                return "extra_point"
    if "punt" in d:                       return "punt"
    if "kickoff" in d:                    return "kickoff"
    if "penalty" in d:                    return "penalty"
    return "other"


def _fetch_week_scoreboard(season: int, season_type: int, week: int) -> list[dict]:
    data = _get(f"{ESPN_BASE}/scoreboard", {
        "seasontype": season_type,
        "season": season,
        "week": week,
        "limit": 20,
    })
    return (data or {}).get("events", [])


def _fetch_game_summary(event_id: str) -> Optional[dict]:
    time.sleep(REQUEST_DELAY)
    return _get(f"{ESPN_BASE}/summary", {"event": event_id})


def _upsert_game_from_event(
    event: dict,
    db: Session,
    abbr_to_id: dict[str, int],
    season_label: str,
) -> Optional[int]:
    event_id = event.get("id", "")
    if not event_id:
        return None

    status_name = event.get("status", {}).get("type", {}).get("name", "")
    is_final = status_name == "STATUS_FINAL"

    competitions = event.get("competitions", [{}])
    comp = competitions[0] if competitions else {}
    competitors = comp.get("competitors", [])

    home_data = next((c for c in competitors if c.get("homeAway") == "home"), None)
    away_data = next((c for c in competitors if c.get("homeAway") == "away"), None)
    if not home_data or not away_data:
        return None

    home_abbr = home_data.get("team", {}).get("abbreviation", "")
    away_abbr = away_data.get("team", {}).get("abbreviation", "")
    home_name  = home_data.get("team", {}).get("displayName", "")
    away_name  = away_data.get("team", {}).get("displayName", "")

    home_id = _resolve_team(home_abbr, home_name, db, abbr_to_id)
    away_id = _resolve_team(away_abbr, away_name, db, abbr_to_id)
    if not home_id or not away_id:
        return None

    home_score = _safe_int(home_data.get("score")) or 0
    away_score = _safe_int(away_data.get("score")) or 0

    date_iso = event.get("date", "")
    try:
        game_date = datetime.fromisoformat(date_iso.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        game_date = datetime.utcnow()

    existing = db.query(Game).filter_by(external_id=event_id, sport=SPORT).first()
    if existing:
        existing.status = "final" if is_final else ("live" if "IN" in status_name else "scheduled")
        existing.home_score = home_score
        existing.away_score = away_score
        db.commit()
        return existing.id
    else:
        game = Game(
            external_id=event_id,
            sport=SPORT,
            home_team_id=home_id,
            away_team_id=away_id,
            game_date=game_date,
            status="final" if is_final else ("live" if "IN" in status_name else "scheduled"),
            home_score=home_score,
            away_score=away_score,
            raw_meta={"season": season_label},
        )
        db.add(game)
        db.flush()
        db.commit()
        return game.id


def _ingest_plays_from_summary(db: Session, game_db_id: int, summary: dict) -> int:
    from backend.db.models import Play
    if db.query(Play).filter_by(game_id=game_db_id).count() > 0:
        return 0

    plays_raw: list[dict] = []
    for drive in summary.get("drives", {}).get("previous", []):
        plays_raw.extend(drive.get("plays", []))

    if not plays_raw:
        plays_raw = summary.get("plays", [])

    rows = []
    for play in plays_raw:
        desc = play.get("text") or play.get("description") or ""
        period_data = play.get("period", {})
        period = period_data.get("number", 1) if isinstance(period_data, dict) else 1
        clock = (play.get("clock") or {}).get("displayValue", "") if isinstance(play.get("clock"), dict) else ""
        home_score = _safe_int(play.get("homeScore"))
        away_score = _safe_int(play.get("awayScore"))
        rows.append(Play(
            game_id=game_db_id,
            period=period,
            clock=str(clock),
            play_type=_classify_nfl_play(desc),
            description=str(desc)[:500],
            player_id=None,
            home_score=home_score,
            away_score=away_score,
        ))

    if rows:
        db.bulk_save_objects(rows)
        db.commit()
    return len(rows)


def _ingest_boxscore(db: Session, game_db_id: int, summary: dict, abbr_to_id: dict[str, int]) -> int:
    boxscore = summary.get("boxscore", {})
    players_sections = boxscore.get("players", [])
    inserted = 0

    for section in players_sections:
        team_info = section.get("team", {})
        team_abbr = team_info.get("abbreviation", "")
        team_id_db = _resolve_team(team_abbr, team_info.get("displayName", ""), db, abbr_to_id)

        for stat_group in section.get("statistics", []):
            keys = stat_group.get("keys", [])
            for athlete_entry in stat_group.get("athletes", []):
                athlete = athlete_entry.get("athlete", {})
                player_name = athlete.get("displayName", "")
                if not player_name:
                    continue
                existing = db.query(PlayerGameStat).filter_by(game_id=game_db_id, player_name=player_name).first()
                if existing:
                    continue

                raw_stats = athlete_entry.get("stats", [])
                stat_dict = dict(zip(keys, raw_stats))

                def gs(k):
                    return _safe_int(stat_dict.get(k))

                db.add(PlayerGameStat(
                    game_id=game_db_id,
                    team_id=team_id_db,
                    player_name=player_name,
                    minutes=None,
                    points=gs("passingTouchdowns") or gs("receivingTouchdowns") or gs("rushingTouchdowns"),
                    assists=None,
                    rebounds=None,
                    offensive_rebounds=None,
                    defensive_rebounds=None,
                    blocks=gs("sacks"),
                    steals=gs("interceptions"),
                    turnovers=gs("fumbles"),
                    fouls=None,
                    field_goals_made=None,
                    field_goals_attempted=None,
                    three_pointers_made=None,
                    three_pointers_attempted=None,
                    free_throws_made=None,
                    free_throws_attempted=None,
                    plus_minus=None,
                    raw=stat_dict,
                ))
                inserted += 1

    if inserted:
        db.commit()
    return inserted


# ─── public API ──────────────────────────────────────────────────────────────

def backfill_historical_nfl(
    num_seasons: int = 5,
    fetch_plays: bool = True,
    fetch_boxscores: bool = True,
) -> None:
    """
    Pull all NFL games + play-by-play + box scores for the last N seasons.
    Safe to run multiple times (idempotent via external_id).
    """
    SessionLocal = get_session_factory()
    db: Session = SessionLocal()

    print(f"\n{'='*60}")
    print(f"NFL Historical Backfill — last {num_seasons} season(s)")
    print(f"  Plays: {fetch_plays}  |  Box Scores: {fetch_boxscores}")
    print(f"{'='*60}\n")

    print("Upserting NFL teams…")
    abbr_to_id = _upsert_nfl_teams(db)

    current_year = datetime.now().year
    seasons = list(range(current_year - num_seasons + 1, current_year + 1))

    total_games = 0
    total_plays = 0
    total_player_stats = 0

    for season in seasons:
        print(f"\n── NFL Season {season} ──")

        all_event_ids: list[tuple[str, int]] = []

        for season_type in SEASON_TYPES:
            type_label = "Regular" if season_type == 2 else "Playoffs"
            max_weeks = MAX_REGULAR_WEEKS if season_type == 2 else MAX_PLAYOFF_WEEKS

            with tqdm(range(1, max_weeks + 1), desc=f"  {type_label} weeks", unit="wk", ncols=80) as pbar:
                for week in pbar:
                    events = _fetch_week_scoreboard(season, season_type, week)
                    time.sleep(REQUEST_DELAY)
                    if not events and week > 1:
                        break  # no more weeks
                    for event in events:
                        db_id = _upsert_game_from_event(event, db, abbr_to_id, str(season))
                        if db_id:
                            all_event_ids.append((event["id"], db_id))
                            total_games += 1
                    pbar.set_postfix(games=total_games)

        if not (fetch_plays or fetch_boxscores):
            continue

        final_events = [
            (eid, dbid) for eid, dbid in all_event_ids
            if db.query(Game).get(dbid) and db.query(Game).get(dbid).status == "final"
        ]
        if fetch_plays:
            final_events = [
                (eid, dbid) for eid, dbid in final_events
                if db.query(Play).filter_by(game_id=dbid).count() == 0
            ]

        if not final_events:
            print(f"  No new games need detail fetch.")
            continue

        with tqdm(final_events, desc=f"  Fetching summaries", unit="game", ncols=80) as pbar:
            for event_id, game_db_id in pbar:
                summary = _fetch_game_summary(event_id)
                if not summary:
                    continue
                if fetch_plays:
                    total_plays += _ingest_plays_from_summary(db, game_db_id, summary)
                if fetch_boxscores:
                    total_player_stats += _ingest_boxscore(db, game_db_id, summary, abbr_to_id)
                pbar.set_postfix(plays=total_plays, stats=total_player_stats)

    db.close()
    print(f"\n{'='*60}")
    print(f"✓ NFL Backfill complete")
    print(f"  Games upserted:    {total_games:,}")
    print(f"  Plays ingested:    {total_plays:,}")
    print(f"  Player stat rows:  {total_player_stats:,}")
    print(f"{'='*60}\n")


def run_live_refresh() -> None:
    """Refresh current week's NFL games (scores + plays for finished games)."""
    SessionLocal = get_session_factory()
    db: Session = SessionLocal()

    print("[NFL Live Refresh] Updating current week…")
    abbr_to_id = _upsert_nfl_teams(db)

    current_year = datetime.now().year
    events = _fetch_week_scoreboard(current_year, 2, week=1)
    # ESPN returns current/latest week when week is omitted or 1 in-season
    # Actually fetch scoreboard with no week to get current
    data = _get(f"{ESPN_BASE}/scoreboard", {"limit": 50})
    events = (data or {}).get("events", []) if data else events

    total = 0
    for event in events:
        db_id = _upsert_game_from_event(event, db, abbr_to_id, str(current_year))
        if db_id:
            total += 1
            game = db.query(Game).get(db_id)
            if game and game.status == "final":
                summary = _fetch_game_summary(event["id"])
                if summary:
                    _ingest_plays_from_summary(db, db_id, summary)
                    _ingest_boxscore(db, db_id, summary, abbr_to_id)

    db.close()
    print(f"[NFL Live Refresh] {total} games updated.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NFL data ingestion")
    parser.add_argument("--mode", choices=["backfill", "live"], default="live")
    parser.add_argument("--seasons", type=int, default=5)
    parser.add_argument("--no-plays", action="store_true")
    parser.add_argument("--no-boxscores", action="store_true")
    args = parser.parse_args()

    if args.mode == "backfill":
        backfill_historical_nfl(
            num_seasons=args.seasons,
            fetch_plays=not args.no_plays,
            fetch_boxscores=not args.no_boxscores,
        )
    else:
        run_live_refresh()
