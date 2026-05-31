"""
Agent 1: Event Feature Extraction
Pure Python analytics — no LLM needed.
Reads plays from DB and computes momentum, key moments, top performers.
"""
from collections import defaultdict
from sqlalchemy.orm import Session

from db.models import GameFeature, Play, Game, Player, Team
from db.session import get_session_factory


def _compute_scoring_runs(plays: list[Play]) -> list[dict]:
    """Detect runs of 6+ consecutive points by one team."""
    runs = []
    home_run = 0
    away_run = 0
    prev_home = 0
    prev_away = 0
    run_start_idx = 0

    for i, p in enumerate(plays):
        if p.home_score is None or p.away_score is None:
            continue
        h, a = p.home_score, p.away_score
        delta_h = h - prev_home
        delta_a = a - prev_away
        if delta_h > 0:
            home_run += delta_h
            away_run = 0
            if home_run >= 6:
                runs.append({"team": "home", "points": home_run, "play_index": i, "clock": p.clock, "period": p.period})
        elif delta_a > 0:
            away_run += delta_a
            home_run = 0
            if away_run >= 6:
                runs.append({"team": "away", "points": away_run, "play_index": i, "clock": p.clock, "period": p.period})
        prev_home, prev_away = h, a

    return runs[-10:]  # top 10 runs


def _find_lead_changes(plays: list[Play]) -> list[dict]:
    changes = []
    prev_leader = None
    for p in plays:
        if p.home_score is None or p.away_score is None:
            continue
        if p.home_score > p.away_score:
            leader = "home"
        elif p.away_score > p.home_score:
            leader = "away"
        else:
            leader = "tie"
        if leader != prev_leader and prev_leader is not None:
            changes.append({"to": leader, "period": p.period, "clock": p.clock,
                            "home": p.home_score, "away": p.away_score})
        prev_leader = leader
    return changes


def _find_key_moments(plays: list[Play], game: Game) -> list[dict]:
    moments = []
    # Clutch time: final period, last 5 min equivalent
    final_period = 4 if game.sport == "NBA" else 4
    clutch_plays = [
        p for p in plays
        if p.period >= final_period and p.description
    ]

    # Score differential ≤5 in final period
    close_plays = [
        p for p in clutch_plays
        if p.home_score is not None and p.away_score is not None
        and abs(p.home_score - p.away_score) <= 5
    ]

    for p in close_plays[-5:]:
        moments.append({
            "type": "clutch",
            "description": p.description,
            "period": p.period,
            "clock": p.clock,
            "score": f"{p.away_score}-{p.home_score}",
        })

    # Biggest plays by type
    for pt in ["dunk", "block", "steal", "touchdown", "interception"]:
        matching = [p for p in plays if p.play_type == pt]
        if matching:
            moments.append({
                "type": pt,
                "description": matching[0].description,
                "period": matching[0].period,
                "clock": matching[0].clock,
            })

    return moments[:15]


def _find_top_performers(plays: list[Play], db: Session) -> list[dict]:
    player_plays: dict[int, list[str]] = defaultdict(list)
    for p in plays:
        if p.player_id:
            player_plays[p.player_id].append(p.play_type)

    scored = []
    for pid, types in player_plays.items():
        score = (
            types.count("dunk") * 5
            + types.count("three_pointer") * 4
            + types.count("block") * 3
            + types.count("steal") * 3
            + types.count("assist") * 2
            + types.count("touchdown") * 6
            + types.count("pass_complete") * 1
        )
        scored.append((pid, score, len(types)))

    top = sorted(scored, key=lambda x: x[1], reverse=True)[:5]
    result = []
    for pid, score, n_plays in top:
        player = db.query(Player).get(pid)
        result.append({
            "player_id": pid,
            "name": player.name if player else "Unknown",
            "impact_score": score,
            "play_count": n_plays,
        })
    return result


async def event_extraction_agent(game_id: int) -> dict:
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        game = db.query(Game).get(game_id)
        if not game:
            return {}

        plays = db.query(Play).filter_by(game_id=game_id).order_by(Play.id).all()
        if not plays:
            return {"game_id": game_id, "plays": 0}

        momentum_shifts = _compute_scoring_runs(plays)
        lead_changes = _find_lead_changes(plays)
        key_moments = _find_key_moments(plays, game)
        top_performers = _find_top_performers(plays, db)

        features_data = {
            "momentum_shifts": momentum_shifts,
            "lead_changes": lead_changes,
            "key_moments": key_moments,
            "top_performers": top_performers,
        }

        existing = db.query(GameFeature).filter_by(game_id=game_id).first()
        if existing:
            existing.momentum_shifts = momentum_shifts
            existing.key_moments = key_moments
            existing.top_performers = top_performers
        else:
            feat = GameFeature(
                game_id=game_id,
                momentum_shifts=momentum_shifts,
                key_moments=key_moments,
                top_performers=top_performers,
            )
            db.add(feat)
        db.commit()

        return features_data
    finally:
        db.close()
