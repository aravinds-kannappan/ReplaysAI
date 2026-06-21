"""AI briefing and what-if scenarios.

Uses the configured LLM (Anthropic first) via api.recaps.llm_text when a key is
set, and falls back to grounded, data-built text otherwise so the dashboard
always has content — free, no key required.
"""
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.recaps import llm_text, _lead_changes
from api.espn_public import (
    extract_summary_leaders,
    extract_summary_plays,
    fetch_espn_game_by_id,
    fetch_espn_summary_by_id,
)

router = APIRouter(prefix="/api", tags=["insights"])


class TeamBrief(BaseModel):
    name: str
    record: Optional[str] = None
    recent: List[str] = Field(default_factory=list)


class PlayerBrief(BaseModel):
    name: str
    line: Optional[str] = None


class BriefingBody(BaseModel):
    sport: str = "NBA"
    teams: List[TeamBrief] = Field(default_factory=list)
    players: List[PlayerBrief] = Field(default_factory=list)


@router.post("/briefing")
def briefing(body: BriefingBody):
    if not body.teams and not body.players:
        return {"content": "Follow teams and players to get a personalized briefing.", "generated_by": "empty"}

    team_lines = "\n".join(
        f"- {t.name}: {t.record or 'record n/a'}" + (f" — recent: {', '.join(t.recent[:5])}" if t.recent else "")
        for t in body.teams
    )
    player_lines = "\n".join(f"- {p.name}: {p.line or 'season stats n/a'}" for p in body.players)

    content = llm_text(
        system=(
            "You are ReplaysAI's daily briefing writer and Stats Agent. Write a detailed, sharp fan "
            "briefing in Markdown (~500-750 words) grounded ONLY in the supplied records, recent "
            "results, and player stat lines — never invent stats. Structure it with: "
            "### Executive read, ### Team form, ### Star player watch, ### Prediction angles, "
            "and ### What to watch next. Be confident, specific, fan-facing, and explain the why."
        ),
        prompt=(
            f"League: {body.sport}\n\nTeams:\n{team_lines or 'none'}\n\nPlayers:\n{player_lines or 'none'}\n\n"
            "Write the detailed briefing now."
        ),
        max_tokens=1500,
    )
    if content:
        return {"content": content, "generated_by": "llm"}

    # Data fallback — still detailed and structured.
    parts = [
        "### Executive read\n",
        (
            f"The {body.sport} briefing is running in data mode, so this read uses only the "
            "teams, records, recent results, and player lines supplied by the dashboard. "
            "The goal is still the same: separate trend from noise, identify which teams are "
            "building momentum, and surface what the fan should watch next."
        ),
        "\n### Team form\n",
    ]
    for t in body.teams:
        rec = t.record or "record n/a"
        wins = losses = None
        if t.record and "-" in t.record:
            try:
                wins, losses = [int(x) for x in t.record.split("-")[:2]]
            except ValueError:
                pass
        trend = ""
        if t.recent:
            wl = [r.split(" ")[0] for r in t.recent]
            w = wl.count("W")
            trend = (
                f" The recent sample is {w}-{len(wl) - w} over the last {len(wl)} tracked games "
                f"({', '.join(t.recent[:5])}). That tells the dashboard whether the current record "
                "is being reinforced by recent form or pulled down by a rough stretch."
            )
        verdict = " The next read should focus on late-game execution and whether the scoring profile is stabilizing."
        if wins is not None and losses is not None:
            verdict = (
                " The model should treat them as a positive-trend team until the margin profile says otherwise."
                if wins > losses * 2 else
                " The model should treat them as competitive but volatile because wins and losses are close."
                if wins >= losses else
                " The model should flag them as a response team: the next win matters, but so does how they get it."
            )
        parts.append(f"**{t.name}** — Current record sample: {rec}.{trend}{verdict}")
    if body.players:
        parts.append("\n### Star player watch\n")
        for p in body.players:
            parts.append(
                f"**{p.name}** — {p.line or 'season stats pending'}. The Stats Agent should connect this line "
                "to game context: production level, role stability, and whether the player is likely to drive "
                "future picks, reels, or roster decisions."
            )
    parts.append(
        "\n### Prediction angles\n"
        "The Prediction Agent should use this as a first-pass model input: recent wins and losses, "
        "scoring direction, and star-player production. This is not betting advice; it is a fan-facing "
        "confidence layer for picks and game previews.\n\n"
        "### What to watch next\n"
        "Open the latest game for a full recap, generate a fan-perspective version if one of your teams played, "
        "then move to the Reels tab for the 2, 5, or 10 minute cut. The most useful next question for the "
        "assistant is: which result changed the outlook the most?"
    )
    return {"content": "\n\n".join(parts), "generated_by": "data"}


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
    leader_lines = "\n".join(f"{r['team']} — {r['player']}: {r['stat_line']} ({r['category']})" for r in leaders[:6])

    content = llm_text(
        system=(
            "You are ReplaysAI's what-if analyst. Given a real game's result and statistical "
            "leaders, write exactly 3 concise, plausible what-if scenarios (each 1-2 sentences) "
            "grounded in the data — e.g. removing a star's production, flipping a key run. "
            "Return them as a markdown bullet list. No invented players."
        ),
        prompt=(
            f"{away.get('name')} {game.get('away_score')} at {home.get('name')} {game.get('home_score')}.\n"
            f"Lead changes: {lead_changes}.\nLeaders:\n{leader_lines or 'n/a'}\n\nWrite 3 what-ifs."
        ),
        max_tokens=400,
    )
    if content:
        return {"scenarios": content, "generated_by": "llm"}

    top = leaders[0] if leaders else None
    bullets = []
    if top:
        bullets.append(f"- Without **{top['player']}**'s {top['stat_line']} {top['category'].lower()}, the result likely swings the other way.")
    bullets.append(f"- This game had **{lead_changes} lead change{'s' if lead_changes != 1 else ''}** — flip the decisive one and the final flips too.")
    bullets.append("- Take away the biggest scoring run and it becomes a one-possession finish.")
    return {"scenarios": "\n".join(bullets), "generated_by": "data"}
