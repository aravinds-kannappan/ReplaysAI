"""
Build the training inputs from REAL ESPN data, reusing the app's own provider
(api/espn_public.py) so the facts match exactly what the API sees at serve time.

Outputs (inputs only; targets are added by distill.py):
  data/broadcast_facts.jsonl    one record per finished game: its `facts` dict
  data/newsletter_facts.jsonl   one record per (synthetic fan profile x ISO week)

Usage:
  python training/espn_dataset.py --sports NBA NFL --seasons 3 --max-games 1500
"""
from __future__ import annotations

import argparse
import json
import os
import random

import _bootstrap  # noqa: F401  (puts repo root on sys.path)

from api.espn_public import (
    fetch_espn_games,
    fetch_espn_summary_by_id,
    fetch_espn_teams,
    extract_summary_plays,
    extract_summary_leaders,
)
from api.recaps import _period_scores, _lead_changes
from api import newsletter as nl


def _is_final(game: dict) -> bool:
    # Scoreline is the source of truth (ESPN mislabels statuses).
    return game.get("home_score") is not None and game.get("away_score") is not None


def _broadcast_facts(sport: str, game: dict) -> dict | None:
    resolved = fetch_espn_summary_by_id(game["id"])
    if not resolved:
        return None
    _, summary = resolved
    plays = extract_summary_plays(summary, sport, limit=400)
    real_plays = [p for p in plays if p.get("play_type") != "other"]
    key_plays = [
        p for p in real_plays
        if any(kw in (p.get("description") or "").lower()
               for kw in ("three", "dunk", "layup", "touchdown", "interception", "sack",
                          "field goal", "three-pointer", "free throw", "buzzer", "overtime"))
    ][-25:]
    return {
        "sport": sport,
        "away": game["away_team"],
        "home": game["home_team"],
        "away_score": game.get("away_score"),
        "home_score": game.get("home_score"),
        "date": (game.get("game_date") or "")[:10],
        "periods": _period_scores(plays, sport),
        "lead_changes": _lead_changes(plays),
        "leaders": extract_summary_leaders(summary),
        "key_plays": key_plays,
    }


def build_broadcast(sports: list[str], seasons: int, max_games: int) -> int:
    out_path = os.path.join(_bootstrap.DATA_DIR, "broadcast_facts.jsonl")
    n = 0
    with open(out_path, "w") as fh:
        for sport in sports:
            games = [g for g in fetch_espn_games(sport, limit=max_games, seasons=seasons) if _is_final(g)]
            for game in games:
                facts = _broadcast_facts(sport, game)
                if not facts or not facts["periods"]:
                    continue
                fh.write(json.dumps({"game_id": game["id"], "facts": facts}) + "\n")
                n += 1
                if n % 50 == 0:
                    print(f"  broadcast: {n} games")
    print(f"broadcast_facts.jsonl: {n} records -> {out_path}")
    return n


def build_newsletter(sports: list[str], seasons: int, profiles_per_week: int, weeks: int) -> int:
    """Synthesize fan profiles (random real-team subsets) and gather each
    profile's real games for a set of recent ISO weeks."""
    out_path = os.path.join(_bootstrap.DATA_DIR, "newsletter_facts.jsonl")
    teams_by_sport = {s: fetch_espn_teams(s) for s in sports}
    # Recent ISO weeks, newest first.
    from datetime import date, timedelta
    today = date.today()
    week_keys = []
    for i in range(weeks):
        d = today - timedelta(weeks=i)
        iso = d.isocalendar()
        week_keys.append(f"{iso[0]}-W{iso[1]:02d}")

    n = 0
    with open(out_path, "w") as fh:
        for week_key in week_keys:
            for _ in range(profiles_per_week):
                sport = random.choice(sports)
                teams = teams_by_sport[sport]
                if not teams:
                    continue
                picks = random.sample(teams, k=min(len(teams), random.choice([1, 2, 3])))
                favorite_teams = [f"{sport}:{t['abbreviation']}" for t in picks]
                games = nl._gather_recent_games(favorite_teams)
                if not games:
                    continue
                fh.write(json.dumps({
                    "display_name": None,
                    "favorite_teams": favorite_teams,
                    "followed_players": [],
                    "week_key": week_key,
                    "games": games,
                }) + "\n")
                n += 1
    print(f"newsletter_facts.jsonl: {n} records -> {out_path}")
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sports", nargs="+", default=["NBA", "NFL"])
    ap.add_argument("--seasons", type=int, default=3)
    ap.add_argument("--max-games", type=int, default=1500)
    ap.add_argument("--profiles-per-week", type=int, default=40)
    ap.add_argument("--weeks", type=int, default=20)
    ap.add_argument("--task", choices=["newsletter", "broadcast", "both"], default="both")
    args = ap.parse_args()

    random.seed(7)
    if args.task in ("broadcast", "both"):
        build_broadcast(args.sports, args.seasons, args.max_games)
    if args.task in ("newsletter", "both"):
        build_newsletter(args.sports, args.seasons, args.profiles_per_week, args.weeks)


if __name__ == "__main__":
    main()
