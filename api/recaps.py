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


# Last provider failure, surfaced in responses that fell back to data
# generation — Vercel function logs are not always at hand.
_last_llm_error: str | None = None


def llm_text(system: str, prompt: str, max_tokens: int = 1500, models: list[str] | None = None) -> str | None:
    """One LLM completion; None when no provider is configured or the call fails.

    `models` overrides the model preference order (e.g. fast-first for
    latency-sensitive callers)."""
    global _last_llm_error
    settings = get_settings()
    _last_llm_error = None

    if settings.anthropic_api_key:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            for model in (models or settings.anthropic_models):
                try:
                    response = client.messages.create(
                        model=model,
                        max_tokens=max_tokens,
                        system=system,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    _last_llm_error = None
                    return response.content[0].text.strip()
                except Exception as exc:
                    _last_llm_error = f"anthropic/{model}: {type(exc).__name__}: {str(exc)[:300]}"
                    print(f"[recaps] {_last_llm_error}")
        except Exception as exc:
            _last_llm_error = f"anthropic/client: {type(exc).__name__}: {str(exc)[:300]}"
            print(f"[recaps] {_last_llm_error}")

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
            _last_llm_error = None
            return (response.choices[0].message.content or "").strip()
        except Exception as exc:
            _last_llm_error = f"openai/{settings.openai_model}: {type(exc).__name__}: {str(exc)[:300]}"
            print(f"[recaps] {_last_llm_error}")

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


def _play_weight(play: dict) -> int:
    weights = {
        "touchdown": 10,
        "dunk": 9,
        "three_pointer": 8,
        "interception": 8,
        "sack": 7,
        "block": 7,
        "steal": 7,
        "field_goal": 6,
        "turnover": 6,
        "assist": 5,
        "shot": 4,
    }
    score = weights.get(play.get("play_type") or "other", 1)
    if "miss" in (play.get("description") or "").lower():
        score = max(1, score - 5)
    return score


def _key_plays(plays: list[dict], limit: int = 16) -> list[dict]:
    interesting = [play for play in plays if play.get("play_type") not in (None, "other")]
    if not interesting:
        interesting = [play for play in plays if play.get("description")]
    if len(interesting) <= limit:
        return interesting
    late = interesting[-max(4, limit // 3):]
    best = sorted(interesting, key=lambda play: (-_play_weight(play), play.get("id") or 0))[:limit]
    selected = {id(play): play for play in best + late}
    return sorted(selected.values(), key=lambda play: play.get("id") or 0)[:limit]


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

## The Story — 3-4 paragraphs on how the game unfolded and why the winner won
## Quarter Flow — period-by-period read using the score by period
## Turning Point — the stretch or plays that decided it, with specifics
## Star Performances — what the statistical leaders actually did and why it mattered
## Tactical Read — pace, pressure, scoring profile, and what changed
## What It Means — stakes and what to watch next for both teams

Aim for 750-1000 words. Be concrete: scores, runs, names, periods."""
    return llm_text(system, prompt, max_tokens=1900)


def _scheduled_preview(facts: dict) -> str:
    """A clean preview for games that have not started — no fake 'in progress' text."""
    away, home = facts["away"], facts["home"]
    leaders = facts["leaders"][:4]
    stars = (
        "Players to watch: "
        + ", ".join(f"{row['player']} ({row['team']})" for row in leaders)
        + "."
        if leaders else "Rosters and projected starters will fill in closer to tip."
    )
    return f"""# {away} at {home} — {facts['date']}
**Scheduled — tip-off preview**

{home} host {away} on {facts['date']}. Once the game is final, this page turns into a full
recap: the decisive run, the star lines, and the moments that swung it.

{stars}

Check back after the final whistle for the complete recap and highlight reel."""


def _data_recap(facts: dict, sport: str) -> str:
    """A readable recap assembled from the play-by-play when no LLM is available."""
    away, home = facts["away"], facts["home"]
    if facts["away_score"] is None or facts["home_score"] is None:
        return _scheduled_preview(facts)

    home_won = facts["home_score"] > facts["away_score"]
    winner, loser = (home, away) if home_won else (away, home)
    win_score, lose_score = (
        (facts["home_score"], facts["away_score"]) if home_won else (facts["away_score"], facts["home_score"])
    )
    margin = abs(facts["home_score"] - facts["away_score"])
    live = facts.get("status") == "live"
    verb = "lead" if live else "beat"
    scoreline = f"{away} {facts['away_score']}, {home} {facts['home_score']}"

    lc = facts["lead_changes"]
    if margin >= 18:
        shape = f"a comfortable {margin}-point win that {winner} controlled."
    elif lc >= 6:
        shape = f"a back-and-forth fight with {lc} lead changes before {winner} pulled away."
    elif margin <= 5:
        shape = f"a tight one decided late, {winner} edging it by {margin}."
    else:
        shape = f"a steady {margin}-point result in {winner}'s favor."

    periods = facts["periods"]
    if periods:
        flow = " → ".join(f"{p['label']} {p['away']}-{p['home']}" for p in periods)
        flow_line = f"The game moved {flow} (away–home). "
    else:
        flow_line = ""

    leaders = facts["leaders"][:4]
    if leaders:
        star_line = (
            f"{leaders[0]['player']} led the way with {leaders[0]['stat_line']} for {leaders[0]['team']}"
        )
        if len(leaders) > 1:
            star_line += ", with " + ", ".join(
                f"{r['player']} adding {r['stat_line']}" for r in leaders[1:3]
            )
        star_line += "."
    else:
        star_line = "Box-score leaders post once the official summary lands."

    headline = f"{winner} {verb} {loser}, {win_score}–{lose_score}"

    moment_rows = []
    for play in facts["key_plays"][:10]:
        label = _period_label(sport, play.get("period") or 1)
        moment_rows.append(f"- **{label} {play.get('clock') or ''}** — {play.get('description')}")
    moment_text = "\n".join(moment_rows) or "- Play-by-play detail will post with the official summary."

    return f"""# {headline}
**{scoreline}** · {facts['date']}

## The Story
{winner} {verb} {loser} {(str(win_score) + '–' + str(lose_score))}, {shape} {flow_line}{star_line}

## How It Unfolded
{flow_line or 'Period-by-period scoring will publish with the official box score.'}

## Star Performances
{star_line}

## Key Moments
{moment_text}"""


def _build_recap(game_id: int, sport: str, game: dict, summary: dict) -> dict:
    plays = extract_summary_plays(summary, sport, limit=300)
    leaders = extract_summary_leaders(summary)
    facts = _game_facts(game, plays, leaders, sport)

    content = None
    generated_by = "data"
    # Generate the full LLM recap whenever the game has been played (both scores
    # present). ESPN's by-id status is unreliable — it sometimes labels finished
    # games "scheduled" — so we key off the scoreline, not the status string.
    played = facts["away_score"] is not None and facts["home_score"] is not None
    if played:
        content = _llm_recap(facts, sport)
        if content:
            generated_by = "llm"
    if not content:
        content = _data_recap(facts, sport)

    result = {
        "game_id": game_id,
        "content": content,
        "status": "ready",
        "generated_by": generated_by,
        "cv_classifications": len(facts["key_plays"]),
    }
    if generated_by == "data" and _last_llm_error:
        result["llm_error"] = _last_llm_error
    return result


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
    settings = get_settings()
    llm_configured = bool(settings.anthropic_api_key or settings.openai_api_key)
    played = game.get("away_score") is not None and game.get("home_score") is not None
    # Cache played games (final/mislabeled), but not obviously-live ones whose
    # numbers keep changing. Never cache a fallback recap when an LLM is
    # configured — a transient provider error would pin the lesser recap.
    if played and game.get("status") != "live" and (result["generated_by"] == "llm" or not llm_configured):
        _memo_set(cache_key, result)
        cache_set(cache_key, result)
    return result


@router.post("/{game_id}/generate")
async def trigger_generation(game_id: int):
    return get_recap(game_id)
