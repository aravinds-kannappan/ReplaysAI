"""
NBA data ingestion via ESPN unofficial API.

Two modes:
  • backfill_historical_nba()  – pulls all games for N past seasons (idempotent)
  • run_live_refresh()         – updates today's / in-progress games only

Run directly:
  python -m ingestion.nba_ingester --mode backfill --seasons 10
  python -m ingestion.nba_ingester --mode live
"""
import argparse
import time
from datetime import date, datetime, timedelta
from typing import Optional

import httpx
from nba_api.stats.static import teams as nba_teams_static
from sqlalchemy.orm import Session
from tqdm import tqdm

from db.models import Game, Play, Player, PlayerGameStat, Team
from db.session import get_session_factory

SPORT = "NBA"
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"

# Approximate NBA season date windows  (season label → (start, end))
NBA_SEASONS = {
    "2015-16": (date(2015, 10, 27), date(2016, 6, 19)),
    "2016-17": (date(2016, 10, 25), date(2017, 6, 12)),
    "2017-18": (date(2017, 10, 17), date(2018, 6, 8)),
    "2018-19": (date(2018, 10, 16), date(2019, 6, 13)),
    "2019-20": (date(2019, 10, 22), date(2020, 10, 11)),
    "2020-21": (date(2020, 12, 22), date(2021, 7, 22)),
    "2021-22": (date(2021, 10, 19), date(2022, 6, 16)),
    "2022-23": (date(2022, 10, 18), date(2023, 6, 12)),
    "2023-24": (date(2023, 10, 24), date(2024, 6, 17)),
    "2024-25": (date(2024, 10, 22), date(2025, 6, 30)),
    "2025-26": (date(2025, 10, 21), date(2026, 6, 30)),
}

REQUEST_DELAY = 0.45  # seconds between ESPN calls


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


def _upsert_nba_teams(db: Session) -> dict[str, int]:
    """Load all 30 NBA static teams, return abbreviation→DB-id map."""
    abbr_to_id: dict[str, int] = {}
    for t in nba_teams_static.get_teams():
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


_ESPN_ABBR_MAP = {
    "GS": "GSW", "SA": "SAS", "NO": "NOP", "NY": "NYK",
    "WSH": "WAS", "UTAH": "UTA", "WSH": "WAS",
}


def _resolve_team(abbr: str, name: str, db: Session, abbr_to_id: dict[str, int]) -> Optional[int]:
    abbr = _ESPN_ABBR_MAP.get(abbr, abbr)
    if abbr in abbr_to_id:
        return abbr_to_id[abbr]
    # fuzzy fallback on last word of team name
    last = name.split()[-1] if name else ""
    t = db.query(Team).filter(Team.name.ilike(f"%{last}%"), Team.sport == SPORT).first()
    if t:
        abbr_to_id[abbr] = t.id
        return t.id
    return None


def _classify_play(desc: str) -> str:
    d = desc.lower()
    if "3pt" in d or "3-pt" in d or "three point" in d:  return "three_pointer"
    if "dunk" in d:         return "dunk"
    if "block" in d:        return "block"
    if "steal" in d:        return "steal"
    if "free throw" in d:   return "free_throw"
    if "turnover" in d:     return "turnover"
    if "assist" in d:       return "assist"
    if "rebound" in d:      return "rebound"
    if "foul" in d:         return "foul"
    return "other"


def _safe_int(v) -> Optional[int]:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


# ─── ESPN fetch helpers ───────────────────────────────────────────────────────

def _fetch_scoreboard_for_date(date_str: str) -> list[dict]:
    """date_str: YYYYMMDD"""
    data = _get(f"{ESPN_BASE}/scoreboard", {"dates": date_str, "limit": 50})
    return (data or {}).get("events", [])


def _fetch_game_summary(event_id: str) -> Optional[dict]:
    time.sleep(REQUEST_DELAY)
    return _get(f"{ESPN_BASE}/summary", {"event": event_id})


def _dates_in_range(start: date, end: date):
    """Yield every date in [start, end]."""
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


# ─── core upsert logic ────────────────────────────────────────────────────────

def _upsert_game_from_event(
    event: dict,
    db: Session,
    abbr_to_id: dict[str, int],
    season_label: str,
) -> Optional[int]:
    """Insert or update a game row. Returns game DB id or None."""
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
        # Update score + status only
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
    """Parse plays from ESPN summary. Returns count inserted."""
    if db.query(Play).filter_by(game_id=game_db_id).count() > 0:
        return 0  # already done

    plays_raw: list[dict] = summary.get("plays", [])
    if not plays_raw:
        for drive in summary.get("drives", {}).get("previous", []):
            plays_raw.extend(drive.get("plays", []))

    if not plays_raw:
        return 0

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
            play_type=_classify_play(desc),
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
    """Parse box score player stats from ESPN summary. Returns player count."""
    boxscore = summary.get("boxscore", {})
    players_sections = boxscore.get("players", [])
    inserted = 0

    for section in players_sections:
        team_info = section.get("team", {})
        team_abbr = team_info.get("abbreviation", "")
        team_id_db = _resolve_team(team_abbr, team_info.get("displayName", ""), db, abbr_to_id)

        statistics = section.get("statistics", [])
        for stat_group in statistics:
            athletes = stat_group.get("athletes", [])
            keys = stat_group.get("keys", [])

            for athlete_entry in athletes:
                athlete = athlete_entry.get("athlete", {})
                player_name = athlete.get("displayName", "")
                if not player_name:
                    continue

                external_player_id = athlete.get("id")
                player = None
                namespaced_player_id = f"{SPORT.lower()}:{external_player_id}" if external_player_id else None
                if namespaced_player_id:
                    player = db.query(Player).filter_by(external_id=namespaced_player_id).first()
                if not player:
                    player = (
                        db.query(Player)
                        .filter(Player.name == player_name, Player.team_id == team_id_db)
                        .first()
                    )
                if not player:
                    player = Player(
                        name=player_name,
                        team_id=team_id_db,
                        position=athlete.get("position", {}).get("abbreviation") if isinstance(athlete.get("position"), dict) else None,
                        jersey_number=_safe_int(athlete.get("jersey")),
                        external_id=namespaced_player_id,
                    )
                    db.add(player)
                    db.flush()

                # Check not already stored
                existing = db.query(PlayerGameStat).filter_by(game_id=game_db_id, player_name=player_name).first()
                if existing:
                    continue

                raw_stats: list[str] = athlete_entry.get("stats", [])
                stat_dict: dict[str, str] = dict(zip(keys, raw_stats))

                def gs(k):
                    return _safe_int(stat_dict.get(k))

                def gf(k):
                    try:
                        return float(stat_dict.get(k, 0) or 0)
                    except (TypeError, ValueError):
                        return 0.0

                # Parse minutes (ESPN sends "MM:SS")
                mins_str = stat_dict.get("minutes", "0:00") or "0:00"
                try:
                    parts = mins_str.split(":")
                    minutes = float(parts[0]) + float(parts[1]) / 60 if len(parts) == 2 else 0.0
                except Exception:
                    minutes = 0.0

                def split_stat(k):
                    """Parse '5-10' style stat → (made, attempted)"""
                    v = stat_dict.get(k, "0-0") or "0-0"
                    parts = v.split("-") if "-" in v else ["0", "0"]
                    return _safe_int(parts[0]), _safe_int(parts[1]) if len(parts) > 1 else None

                fg_m, fg_a = split_stat("fieldGoals") if "fieldGoals" in stat_dict else (gs("fieldGoalsMade"), gs("fieldGoalsAttempted"))
                tp_m, tp_a = split_stat("threePointFieldGoals") if "threePointFieldGoals" in stat_dict else (gs("threePointFieldGoalsMade"), gs("threePointFieldGoalsAttempted"))
                ft_m, ft_a = split_stat("freeThrows") if "freeThrows" in stat_dict else (gs("freeThrowsMade"), gs("freeThrowsAttempted"))

                db.add(PlayerGameStat(
                    game_id=game_db_id,
                    player_id=player.id,
                    team_id=team_id_db,
                    player_name=player_name,
                    minutes=minutes,
                    points=gs("points") or gs("PTS"),
                    assists=gs("assists") or gs("AST"),
                    rebounds=gs("rebounds") or gs("totalRebounds") or gs("REB"),
                    offensive_rebounds=gs("offensiveRebounds") or gs("OREB"),
                    defensive_rebounds=gs("defensiveRebounds") or gs("DREB"),
                    blocks=gs("blocks") or gs("BLK"),
                    steals=gs("steals") or gs("STL"),
                    turnovers=gs("turnovers") or gs("TO"),
                    fouls=gs("fouls") or gs("PF"),
                    field_goals_made=fg_m,
                    field_goals_attempted=fg_a,
                    three_pointers_made=tp_m,
                    three_pointers_attempted=tp_a,
                    free_throws_made=ft_m,
                    free_throws_attempted=ft_a,
                    plus_minus=gf("plusMinus"),
                    raw=stat_dict,
                ))
                inserted += 1

    if inserted:
        db.commit()
    return inserted


# ─── public API ──────────────────────────────────────────────────────────────

def backfill_historical_nba(num_seasons: int = 5, fetch_plays: bool = True, fetch_boxscores: bool = True) -> None:
    """
    Pull all games + play-by-play + box scores for the last N seasons.
    Safe to run multiple times (idempotent via external_id).
    """
    SessionLocal = get_session_factory()
    db: Session = SessionLocal()

    print(f"\n{'='*60}")
    print(f"NBA Historical Backfill — last {num_seasons} season(s)")
    print(f"  Plays: {fetch_plays}  |  Box Scores: {fetch_boxscores}")
    print(f"{'='*60}\n")

    print("Upserting NBA teams…")
    abbr_to_id = _upsert_nba_teams(db)

    seasons = list(NBA_SEASONS.items())[-num_seasons:]
    total_games = 0
    total_plays = 0
    total_player_stats = 0

    for season_label, (start_dt, end_dt) in seasons:
        print(f"\n── Season {season_label} ({start_dt} → {end_dt}) ──")

        # Build list of dates
        all_dates = list(_dates_in_range(start_dt, min(end_dt, date.today())))
        game_ids_this_season: list[tuple[str, int]] = []  # (event_id, db_id)

        with tqdm(all_dates, desc=f"  Fetching game metadata", unit="day", ncols=80) as pbar:
            for d in pbar:
                date_str = d.strftime("%Y%m%d")
                events = _fetch_scoreboard_for_date(date_str)
                time.sleep(REQUEST_DELAY)
                for event in events:
                    db_id = _upsert_game_from_event(event, db, abbr_to_id, season_label)
                    if db_id:
                        game_ids_this_season.append((event["id"], db_id))
                        total_games += 1

        if not (fetch_plays or fetch_boxscores):
            continue

        # Filter to final games that need detail
        final_events = [
            (eid, dbid)
            for eid, dbid in game_ids_this_season
            if db.query(Game).get(dbid) and db.query(Game).get(dbid).status == "final"
        ]
        # Skip games that already have plays
        if fetch_plays:
            final_events = [
                (eid, dbid) for eid, dbid in final_events
                if db.query(Play).filter_by(game_id=dbid).count() == 0
            ]

        if not final_events:
            print(f"  No new games need play-by-play fetch.")
            continue

        with tqdm(final_events, desc=f"  Fetching summaries", unit="game", ncols=80) as pbar:
            for event_id, game_db_id in pbar:
                summary = _fetch_game_summary(event_id)
                if not summary:
                    continue

                if fetch_plays:
                    n_plays = _ingest_plays_from_summary(db, game_db_id, summary)
                    total_plays += n_plays

                if fetch_boxscores:
                    n_stats = _ingest_boxscore(db, game_db_id, summary, abbr_to_id)
                    total_player_stats += n_stats

                pbar.set_postfix(plays=total_plays, stats=total_player_stats)

    db.close()
    print(f"\n{'='*60}")
    print(f"✓ NBA Backfill complete")
    print(f"  Games upserted:       {total_games:,}")
    print(f"  Plays ingested:       {total_plays:,}")
    print(f"  Player stat rows:     {total_player_stats:,}")
    print(f"{'='*60}\n")


def run_live_refresh(days_back: int = 3) -> None:
    """
    Lightweight refresh: update scores for recent/live games.
    Does NOT re-fetch play-by-play for already-ingested games.
    """
    SessionLocal = get_session_factory()
    db: Session = SessionLocal()

    print(f"[NBA Live Refresh] Updating last {days_back} days…")
    abbr_to_id = _upsert_nba_teams(db)

    total_updated = 0
    total_plays = 0

    for day_offset in range(days_back):
        d = date.today() - timedelta(days=day_offset)
        events = _fetch_scoreboard_for_date(d.strftime("%Y%m%d"))
        time.sleep(REQUEST_DELAY)

        for event in events:
            db_id = _upsert_game_from_event(event, db, abbr_to_id, "2024-25")
            if not db_id:
                continue
            total_updated += 1

            game = db.query(Game).get(db_id)
            is_final = game and game.status == "final"
            has_plays = db.query(Play).filter_by(game_id=db_id).count() > 0

            if is_final and not has_plays:
                summary = _fetch_game_summary(event["id"])
                if summary:
                    total_plays += _ingest_plays_from_summary(db, db_id, summary)
                    _ingest_boxscore(db, db_id, summary, abbr_to_id)

    db.close()
    print(f"[NBA Live Refresh] {total_updated} games updated, {total_plays} new plays.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NBA data ingestion")
    parser.add_argument("--mode", choices=["backfill", "live"], default="live")
    parser.add_argument("--seasons", type=int, default=10, help="Number of seasons to backfill")
    parser.add_argument("--no-plays", action="store_true", help="Skip play-by-play (faster)")
    parser.add_argument("--no-boxscores", action="store_true", help="Skip box scores")
    args = parser.parse_args()

    if args.mode == "backfill":
        backfill_historical_nba(
            num_seasons=args.seasons,
            fetch_plays=not args.no_plays,
            fetch_boxscores=not args.no_boxscores,
        )
    else:
        run_live_refresh()
