"""
Personalized feed and fan-perspective recap endpoints.
"""
from fastapi import APIRouter, HTTPException, Query

from api.espn_public import (
    extract_summary_leaders,
    extract_summary_plays,
    fetch_espn_games,
    fetch_espn_game_by_id,
    fetch_espn_summary_by_id,
)
from api.recaps import _memo_get, _memo_set, llm_text
from cache.redis_client import cache_get, cache_set

router = APIRouter(prefix="/api", tags=["feed"])


def _parse_favorite_keys(raw: str | None) -> set[tuple[str, str]]:
    keys = set()
    for item in (raw or "").split(","):
        if ":" not in item:
            continue
        sport, abbreviation = item.split(":", 1)
        if sport and abbreviation:
            keys.add((sport.upper(), abbreviation.upper()))
    return keys


def _game_team_keys(game: dict) -> set[tuple[str, str]]:
    sport = game.get("sport", "").upper()
    return {
        (sport, (game.get("home_team") or {}).get("abbreviation", "").upper()),
        (sport, (game.get("away_team") or {}).get("abbreviation", "").upper()),
    }


@router.get("/feed")
def get_personalized_feed(
    limit: int = 20,
    favorite_teams: str | None = Query(None),
):
    favorite_keys = _parse_favorite_keys(favorite_teams)
    rows = []
    # When filtering by favorites, keep everything each season window returns
    # (the scoreboard call fetches up to 100 games regardless), otherwise a
    # per-window truncation leaves only finals games and favorite teams that
    # missed deep playoff runs never show up.
    fetch_limit = 1000 if favorite_keys else limit
    for sport in ("NBA", "NFL"):
        for game in fetch_espn_games(sport, limit=fetch_limit, seasons=10):
            if favorite_keys and not (favorite_keys & _game_team_keys(game)):
                continue
            rows.append(game)
    rows = sorted(rows, key=lambda game: game.get("game_date") or "", reverse=True)[:limit]
    return {
        "games": rows,
        "favorite_team_ids": [],
        "favorite_team_keys": [f"{sport}:{abbr}" for sport, abbr in sorted(favorite_keys)],
        "onboarded": bool(favorite_keys),
    }


def _fan_recap_key(game_id: int, team: str | None) -> str:
    return f"fan_recap:v2:{game_id}:{(team or '').upper()}"


@router.get("/games/{game_id}/fan-recap")
def get_fan_recap(game_id: int, team: str | None = Query(None)):
    key = _fan_recap_key(game_id, team)
    cached = _memo_get(key) or cache_get(key)
    if cached:
        return cached
    return {"game_id": game_id, "content": None, "status": "not_generated"}


@router.post("/games/{game_id}/fan-recap/generate")
async def generate_fan_recap(game_id: int, team: str | None = Query(None)):
    resolved_game = fetch_espn_game_by_id(game_id)
    resolved_summary = fetch_espn_summary_by_id(game_id)
    if not resolved_game or not resolved_summary:
        raise HTTPException(status_code=404, detail="Game not found")
    sport, game = resolved_game
    _, summary = resolved_summary

    away, home = game["away_team"], game["home_team"]
    fan_team = home if (team or "").upper() == (home.get("abbreviation") or "").upper() else away
    other_team = home if fan_team is away else away
    fan_score = game["home_score"] if fan_team is home else game["away_score"]
    other_score = game["home_score"] if other_team is home else game["away_score"]

    leaders = extract_summary_leaders(summary)
    plays = [p for p in extract_summary_plays(summary, sport, limit=300) if p.get("play_type") != "other"][-12:]
    leader_lines = "\n".join(f"{r['team']} — {r['player']}: {r['stat_line']} ({r['category']})" for r in leaders)
    play_lines = "\n".join(
        f"P{p.get('period')} {p.get('clock') or ''}: {p.get('description')}" for p in plays
    )

    won = fan_score is not None and other_score is not None and fan_score > other_score
    tone = (
        "Your team WON — write with energy and celebration, but stay specific about how they did it."
        if won else
        "Your team LOST — write an honest, clear-eyed post-mortem. No sugarcoating, no despair; what went wrong and what's fixable."
    )

    content = llm_text(
        system=(
            f"You write game recaps for die-hard {fan_team.get('name')} fans, from their perspective "
            "('we', 'our'). Ground everything strictly in the provided data — never invent stats or plays. "
            "Output Markdown, 250-400 words."
        ),
        prompt=(
            f"{tone}\n\nGame: {away.get('name')} {game.get('away_score')} at "
            f"{home.get('name')} {game.get('home_score')} ({(game.get('game_date') or '')[:10]})\n\n"
            f"Statistical leaders:\n{leader_lines or 'not available'}\n\n"
            f"Late notable plays:\n{play_lines or 'not available'}"
        ),
        max_tokens=900,
    )

    if not content:
        verdict = "took this one" if won else "came up short"
        leader_rows = "\n".join(
            f"- **{r['player']}** ({r['team']}) — {r['stat_line']} {r['category'].lower()}" for r in leaders
        ) or "- Leaders not published yet."
        content = (
            f"# {fan_team.get('name')} {verdict}, "
            f"{fan_score if fan_score is not None else '—'}-{other_score if other_score is not None else '—'}\n\n"
            f"## How It Went\nAgainst {other_team.get('name')} on {(game.get('game_date') or '')[:10]}, "
            f"the scoreboard ended {away.get('name')} {game.get('away_score')}, {home.get('name')} {game.get('home_score')}.\n\n"
            f"## Who Showed Up\n{leader_rows}"
        )

    result = {"game_id": game_id, "content": content, "status": "ready", "team": fan_team.get("abbreviation")}
    key = _fan_recap_key(game_id, team)
    _memo_set(key, result)
    cache_set(key, result)
    return result
