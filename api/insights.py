"""What-if scenarios for a finished game.

Uses the configured LLM (Anthropic first) via api.recaps.llm_text when a key is
set, and falls back to grounded, data-built text otherwise so the feature always
has content: free, no key required.
"""
from fastapi import APIRouter

from api.recaps import llm_text, _lead_changes
from api.espn_public import (
    extract_summary_leaders,
    extract_summary_plays,
    fetch_espn_game_by_id,
    fetch_espn_summary_by_id,
)
from config import get_settings

router = APIRouter(prefix="/api", tags=["insights"])


def _game_facts(game_id: int):
    rg = fetch_espn_game_by_id(game_id)
    rs = fetch_espn_summary_by_id(game_id)
    if not rg or not rs:
        return None
    sport, game = rg
    _, summary = rs
    plays = extract_summary_plays(summary, sport, limit=400)
    leaders = extract_summary_leaders(summary)
    return sport, game, plays, leaders


@router.get("/games/{game_id}/whatif")
def whatif(game_id: int):
    facts = _game_facts(game_id)
    if not facts:
        return {"scenarios": [], "generated_by": "empty"}
    sport, game, plays, leaders = facts
    away, home = game["away_team"], game["home_team"]
    lead_changes = _lead_changes(plays)
    leader_lines = "\n".join(f"{r['team']} · {r['player']}: {r['stat_line']} ({r['category']})" for r in leaders[:6])

    content = llm_text(
        system=(
            "You are ReplaysAI's what-if analyst. Given a real game's result and statistical "
            "leaders, write exactly 3 concise, plausible what-if scenarios (each 1-2 sentences) "
            "grounded in the data, e.g. removing a star's production, flipping a key run. "
            "Return them as a markdown bullet list. No invented players."
        ),
        prompt=(
            f"{away.get('name')} {game.get('away_score')} at {home.get('name')} {game.get('home_score')}.\n"
            f"Lead changes: {lead_changes}.\nLeaders:\n{leader_lines or 'n/a'}\n\nWrite 3 what-ifs."
        ),
        max_tokens=400,
        models=get_settings().anthropic_fast_models,
    )
    if content:
        return {"scenarios": content, "generated_by": "llm"}

    top = leaders[0] if leaders else None
    bullets = []
    if top:
        bullets.append(f"- Without **{top['player']}**'s {top['stat_line']} {top['category'].lower()}, the result likely swings the other way.")
    bullets.append(f"- This game had **{lead_changes} lead change{'s' if lead_changes != 1 else ''}**. Flip the decisive one and the final flips too.")
    bullets.append("- Take away the biggest scoring run and it becomes a one-possession finish.")
    return {"scenarios": "\n".join(bullets), "generated_by": "data"}
