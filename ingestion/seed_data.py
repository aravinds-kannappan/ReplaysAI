"""
seed_data.py — Master backfill script for Replays AI.

Usage:
  python -m ingestion.seed_data               # all sports, 5 seasons
  python -m ingestion.seed_data --sport nba   # NBA only
  python -m ingestion.seed_data --sport nfl   # NFL only
  python -m ingestion.seed_data --seasons 2   # last 2 seasons
  python -m ingestion.seed_data --metadata-only  # games only, no plays

Backfill is fully idempotent — safe to run again after a crash.
Progress bars show real-time status via tqdm.
"""
import argparse
import sys
import time
from datetime import datetime

from db.models import Base, Badge
from db.session import get_engine, get_session_factory


BADGE_SEEDS = [
    {"slug": "week1",    "name": "First Pick",  "description": "Made your first prediction",    "icon": "🎯", "threshold": 1},
    {"slug": "oracle",   "name": "Oracle",       "description": "10 correct predictions",        "icon": "🔮", "threshold": 10},
    {"slug": "loyal",    "name": "Loyal Fan",    "description": "7-day login streak",            "icon": "🔥", "threshold": 7},
    {"slug": "superfan", "name": "Superfan",     "description": "30-day login streak",           "icon": "🏆", "threshold": 30},
    {"slug": "analyst",  "name": "Analyst",      "description": "Generated 10 recaps",           "icon": "📊", "threshold": 10},
    {"slug": "clutch",   "name": "Clutch",       "description": "Predicted within 5 pts",        "icon": "⏱️",  "threshold": 1},
]


def ensure_schema() -> None:
    print("Ensuring DB schema is up to date…")
    Base.metadata.create_all(bind=get_engine())
    print("  ✓ Schema OK")


def seed_badges() -> None:
    db = get_session_factory()()
    added = 0
    for seed in BADGE_SEEDS:
        if not db.query(Badge).filter_by(slug=seed["slug"]).first():
            db.add(Badge(**seed))
            added += 1
    db.commit()
    db.close()
    if added:
        print(f"  ✓ Seeded {added} badge(s)")


def print_header(text: str) -> None:
    bar = "=" * 60
    print(f"\n{bar}")
    print(f"  {text}")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{bar}")


def run_nba_backfill(seasons: int, fetch_plays: bool, fetch_boxscores: bool) -> None:
    from ingestion.nba_ingester import backfill_historical_nba
    backfill_historical_nba(
        num_seasons=seasons,
        fetch_plays=fetch_plays,
        fetch_boxscores=fetch_boxscores,
    )


def run_nfl_backfill(seasons: int, fetch_plays: bool, fetch_boxscores: bool) -> None:
    from ingestion.nfl_ingester import backfill_historical_nfl
    backfill_historical_nfl(
        num_seasons=seasons,
        fetch_plays=fetch_plays,
        fetch_boxscores=fetch_boxscores,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replays AI — full historical data backfill",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--sport", choices=["nba", "nfl", "all"], default="all",
                        help="Sport to backfill (default: all)")
    parser.add_argument("--seasons", type=int, default=5,
                        help="Number of past seasons to fetch (default: 5)")
    parser.add_argument("--metadata-only", action="store_true",
                        help="Only fetch game metadata — skip play-by-play & box scores (fast)")
    parser.add_argument("--no-boxscores", action="store_true",
                        help="Skip box score / player stats fetch")

    args = parser.parse_args()

    fetch_plays = not args.metadata_only
    fetch_boxscores = not args.metadata_only and not args.no_boxscores

    print_header("Replays AI — Historical Data Backfill")
    print(f"  Sport:        {args.sport.upper()}")
    print(f"  Seasons:      {args.seasons}")
    print(f"  Fetch plays:  {fetch_plays}")
    print(f"  Box scores:   {fetch_boxscores}")

    # 1. Schema + badges
    ensure_schema()
    seed_badges()

    t0 = time.time()

    # 2. NBA
    if args.sport in ("nba", "all"):
        run_nba_backfill(args.seasons, fetch_plays, fetch_boxscores)

    # 3. NFL
    if args.sport in ("nfl", "all"):
        run_nfl_backfill(args.seasons, fetch_plays, fetch_boxscores)

    elapsed = time.time() - t0
    mins, secs = divmod(int(elapsed), 60)
    print(f"\n{'='*60}")
    print(f"  ✓ All done in {mins}m {secs}s")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
