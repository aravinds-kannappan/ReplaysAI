import threading
import time

from fastapi import APIRouter, HTTPException

from api.espn_public import (
    extract_summary_leaders,
    extract_summary_plays,
    fetch_espn_game_by_id,
    fetch_espn_summary_by_id,
)
from cache.redis_client import cache_get, cache_set
from config import get_settings

router = APIRouter(prefix="/api/games", tags=["recaps"])

# Warm serverless instances keep finished-game recaps here so an LLM recap is
# generated once per game per instance even when Redis is not configured.
_RECAP_TTL_SECONDS = 6 * 3600
_recap_cache: dict[str, tuple[float, dict]] = {}
_recap_lock = threading.Lock()


def _memo_get(key: str) -> dict | None:
    with _recap_lock:
        hit = _recap_cache.get(key)
        if hit and time.monotonic() - hit[0] < _RECAP_TTL_SECONDS:
            return hit[1]
    return None


def _memo_set(key: str, value: dict) -> None:
    with _recap_lock:
        if len(_recap_cache) > 128:
            _recap_cache.clear()
        _recap_cache[key] = (time.monotonic(), value)


def llm_text(system: str, prompt: str, max_tokens: int = 1500) -> str | None:
    """One LLM completion; None when no provider is configured or the call fails."""
    settings = get_settings()

    if settings.anthropic_api_key:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            response = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception as exc:
            print(f"[recaps] Anthropic call failed ({settings.anthropic_model}): {exc}")

    if settings.openai_api_key:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key)
            response = client.chat.completions.create(
                model=settings.openai_model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as exc:
            print(f"[recaps] OpenAI call failed ({settings.openai_model}): {exc}")

    return None


def _period_label(sport: str, period: int) -> str:
    if sport == "NFL" or period <= 4:
        return f"Q{period}"
    return f"OT{period - 4}"


def _period_scores(plays: list[dict], sport: str) -> list[dict]:
    """Score at the end of each period, taken from the last play with a score."""
    by_period: dict[int, dict] = {}
    for play in plays:
        if play.get("home_score") is None or play.get("away_score") is None:
            continue
        by_period[play.get("period") or 1] = play
    return [
        {
            "label": _period_label(sport, period),
            "away": by_period[period]["away_score"],
            "home": by_period[period]["home_score"],
        }
        for period in sorted(by_period)
    ]


def _lead_changes(plays: list[dict]) -> int:
    changes = 0
    last_leader = 0
    for play in plays:
        home, away = play.get("home_score"), play.get("away_score")
        if home is None or away is None or home == away:
            continue
        leader = 1 if home > away else -1
        if last_leader and leader != last_leader:
            changes += 1
        last_leader = leader
    return changes


def _key_plays(plays: list[dict], limit: int = 10) -> list[dict]:
    interesting = [play for play in plays if play.get("play_type") not in (None, "other")]
    if not interesting:
        interesting = [play for play in plays if play.get("description")]
    return interesting[-limit:]


def _game_facts(game: dict, plays: list[dict], leaders: list[dict], sport: str) -> dict:
    away, home = game["away_team"], game["home_team"]
    return {
        "away": away.get("name") or "Away",
        "home": home.get("name") or "Home",
        "away_abbr": away.get("abbreviation") or "AWY",
        "home_abbr": home.get("abbreviation") or "HME",
        "away_score": game.get("away_score"),
        "home_score": game.get("home_score"),
        "date": (game.get("game_date") or "")[:10],
        "status": game.get("status"),
        "periods": _period_scores(plays, sport),
        "lead_changes": _lead_changes(plays),
        "key_plays": _key_plays(plays),
        "leaders": leaders,
    }


def _llm_recap(facts: dict, sport: str) -> str | None:
    period_lines = "\n".join(
        f"{p['label']}: {facts['away_abbr']} {p['away']} - {facts['home_abbr']} {p['home']}"
        for p in facts["periods"]
    )
    leader_lines = "\n".join(
        f"{row['team']} — {row['player']}: {row['stat_line']} ({row['category']})"
        for row in facts["leaders"]
    )
    play_lines = "\n".join(
        f"{_period_label(sport, play.get('period') or 1)} {play.get('clock') or ''} "
        f"[{facts['away_abbr']} {play.get('away_score')}-{play.get('home_score')} {facts['home_abbr']}] "
        f"{play.get('description')}"
        for play in facts["key_plays"]
    )
    system = (
        "You are a veteran sports beat writer. Write vivid, specific, detailed game "
        "recaps grounded strictly in the data provided — never invent stats, plays, or "
        "quotes. Use the players' names and exact numbers from the data. Output Markdown."
    )
    prompt = f"""Write a detailed recap of this {sport} game.

Matchup: {facts['away']} at {facts['home']}, {facts['date']}
Final score: {facts['away']} {facts['away_score']}, {facts['home']} {facts['home_score']}
Lead changes: {facts['lead_changes']}

Score by period:
{period_lines or 'not available'}

Statistical leaders:
{leader_lines or 'not available'}

Notable plays (chronological, with score at the time):
{play_lines or 'not available'}

Structure the recap as Markdown with exactly these sections:
# <a punchy headline naming the decisive player or storyline>
**{facts['away']} {facts['away_score']}, {facts['home']} {facts['home_score']}**

## The Story — 2-3 paragraphs on how the game unfolded and why the winner won
## Turning Point — the stretch or plays that decided it, with specifics
## Star Performances — what the statistical leaders actually did and why it mattered
## What It Means — stakes and what to watch next for both teams

Aim for 450-650 words. Be concrete: scores, runs, names, periods."""
    return llm_text(system, prompt)


def _data_recap(facts: dict, sport: str) -> str:
    """Detailed recap assembled directly from the play-by-play when no LLM is configured."""
    away, home = facts["away"], facts["home"]
    if facts["away_score"] is not None and facts["home_score"] is not None:
        winner = home if facts["home_score"] > facts["away_score"] else away
        margin = abs(facts["home_score"] - facts["away_score"])
        scoreline = f"{away} {facts['away_score']}, {home} {facts['home_score']}"
        story = (
            f"{winner} won by {margin} in a game with {facts['lead_changes']} lead "
            f"change{'s' if facts['lead_changes'] != 1 else ''}."
        )
    else:
        scoreline = f"{away} at {home}"
        story = "This matchup is still in progress — the numbers below update as it plays out."

    period_rows = "\n".join(
        f"| {p['label']} | {p['away']} | {p['home']} |" for p in facts["periods"]
    )
    period_table = (
        f"| Period | {facts['away_abbr']} | {facts['home_abbr']} |\n|---|---|---|\n{period_rows}"
        if period_rows else "Period-by-period scoring has not been published yet."
    )
    leader_rows = "\n".join(
        f"- **{row['player']}** ({row['team']}) — {row['stat_line']} {row['category'].lower()}"
        for row in facts["leaders"]
    ) or "- Box score leaders have not been published yet."
    moment_rows = "\n".join(
        f"- {_period_label(sport, play.get('period') or 1)} {play.get('clock') or ''} — "
        f"{play.get('description')} "
        f"({facts['away_abbr']} {play.get('away_score')}-{play.get('home_score')} {facts['home_abbr']})"
        for play in facts["key_plays"]
    ) or "- Play-by-play detail has not been published yet."

    return f"""# {away} at {home} — {facts['date']}
**{scoreline}**

## The Story
{story}

## Scoring by Period
{period_table}

## Statistical Leaders
{leader_rows}

## Key Moments
{moment_rows}
"""


def _build_recap(game_id: int, sport: str, game: dict, summary: dict) -> dict:
    plays = extract_summary_plays(summary, sport, limit=300)
    leaders = extract_summary_leaders(summary)
    facts = _game_facts(game, plays, leaders, sport)

    content = None
    generated_by = "data"
    # LLM recaps only for finished games: live numbers go stale immediately and
    # every regeneration costs an inference call.
    if game.get("status") == "final":
        content = _llm_recap(facts, sport)
        if content:
            generated_by = "llm"
    if not content:
        content = _data_recap(facts, sport)

    return {
        "game_id": game_id,
        "content": content,
        "status": "ready",
        "generated_by": generated_by,
        "cv_classifications": len(facts["key_plays"]),
    }


@router.get("/{game_id}/recap")
def get_recap(game_id: int):
    cache_key = f"recap:v2:{game_id}"
    cached = _memo_get(cache_key) or cache_get(cache_key)
    if cached:
        return cached

    resolved_game = fetch_espn_game_by_id(game_id)
    resolved_summary = fetch_espn_summary_by_id(game_id)
    if not resolved_game or not resolved_summary:
        raise HTTPException(status_code=404, detail="Game not found")
    sport, game = resolved_game
    _, summary = resolved_summary

    result = _build_recap(game_id, sport, game, summary)
    if game.get("status") == "final":
        _memo_set(cache_key, result)
        cache_set(cache_key, result)
    return result


@router.post("/{game_id}/generate")
async def trigger_generation(game_id: int):
    return get_recap(game_id)
