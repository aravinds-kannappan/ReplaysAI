"""
Personalized weekly newsletter generator.

One newsletter per user per ISO week. Cached in Supabase — Claude is only
called once per user per week. The content is a Markdown document with
publication-style sections.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.espn_public import fetch_espn_games
from api.recaps import llm_text
from config import get_settings

router = APIRouter(prefix="/api/newsletter", tags=["newsletter"])


def _current_week_key() -> str:
    today = date.today()
    iso = today.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


class NewsletterBody(BaseModel):
    user_id: str
    display_name: str | None = None
    favorite_teams: list[str] = []   # "SPORT:ABBR"
    followed_players: list[str] = []
    week_key: str | None = None      # override; defaults to current ISO week


def _gather_recent_games(favorite_teams: list[str]) -> list[dict]:
    sports = list({t.split(":")[0].upper() for t in favorite_teams if ":" in t}) or ["NBA", "NFL"]
    abbrs = {t.split(":")[1].upper() for t in favorite_teams if ":" in t}
    games: list[dict] = []
    seen: set[int] = set()
    for sport in sports:
        for g in fetch_espn_games(sport, limit=40, seasons=1):
            if g.get("id") in seen:
                continue
            h = (g.get("home_team") or {}).get("abbreviation", "").upper()
            a = (g.get("away_team") or {}).get("abbreviation", "").upper()
            if abbrs and not (abbrs & {h, a}):
                continue
            if g.get("away_score") is None:
                continue
            seen.add(g["id"])
            games.append(g)
    games.sort(key=lambda g: g.get("game_date") or "", reverse=True)
    return games[:12]


def _build_newsletter_llm(
    display_name: str | None,
    favorite_teams: list[str],
    followed_players: list[str],
    games: list[dict],
    week_key: str,
) -> str | None:
    settings = get_settings()
    if not settings.anthropic_api_key:
        return None

    team_names = ", ".join(favorite_teams) or "no specific teams"
    player_names = ", ".join(followed_players[:10]) or "no specific players"
    fan_name = display_name or "Fan"

    game_lines: list[str] = []
    for g in games[:10]:
        ht = (g.get("home_team") or {}).get("name", "?")
        at = (g.get("away_team") or {}).get("name", "?")
        hs = g.get("home_score")
        as_ = g.get("away_score")
        date_str = (g.get("game_date") or "")[:10]
        status = g.get("status", "final")
        game_lines.append(f"- {at} {as_} @ {ht} {hs} ({status}, {date_str})")
    games_block = "\n".join(game_lines) or "No recent game data available."

    system = (
        "You are ReplaysAI's newsletter writer. Generate a personalized weekly sports digest "
        "for this fan. Write in a confident, engaging magazine voice — specific, analytical, with "
        "personality. Use only the data provided; never invent stats, results, or injuries.\n\n"
        "Format as Markdown with these EXACT sections:\n"
        "## Week in Review\n"
        "## Your Players This Week\n"
        "## Games to Watch\n"
        "## The Take\n"
        "## Dream Team Tip\n\n"
        "Aim for 500-700 words total. Make it feel personal to this fan's teams and players."
    )
    prompt = (
        f"Fan: {fan_name}\n"
        f"Teams followed: {team_names}\n"
        f"Players followed: {player_names}\n"
        f"Week: {week_key}\n\n"
        f"Recent game results:\n{games_block}\n\n"
        "Write the newsletter."
    )

    return llm_text(system=system, prompt=prompt, max_tokens=1400)


def _build_newsletter_fallback(
    display_name: str | None,
    favorite_teams: list[str],
    followed_players: list[str],
    games: list[dict],
    week_key: str,
) -> str:
    fan_name = display_name or "Fan"
    team_str = ", ".join(favorite_teams) or "your teams"
    player_str = ", ".join(followed_players[:6]) or "your followed players"

    lines = [
        f"# ReplaysAI Weekly — {week_key}",
        f"*Your personalized sports digest, {fan_name}.*",
        "",
        "## Week in Review",
    ]
    if games:
        for g in games[:5]:
            ht = (g.get("home_team") or {}).get("name", "?")
            at = (g.get("away_team") or {}).get("name", "?")
            hs = g.get("home_score", "—")
            as_ = g.get("away_score", "—")
            date_str = (g.get("game_date") or "")[:10]
            winner = ht if (g.get("home_score") or 0) >= (g.get("away_score") or 0) else at
            lines.append(f"- **{winner}** won: {at} {as_} @ {ht} {hs} ({date_str})")
    else:
        lines.append(f"No recent results found for {team_str}. Check back as the season progresses.")

    lines += [
        "",
        "## Your Players This Week",
        f"Season statistics for {player_str} are available on the Dashboard under Player Stats.",
        "",
        "## Games to Watch",
        f"Upcoming games for {team_str} will appear in your feed as they are scheduled.",
        "",
        "## The Take",
        f"Based on recent results, your teams are in the mix. The season is long — one week can shift "
        "the narrative completely. Keep an eye on the Prediction desk for model reads before each game.",
        "",
        "## Dream Team Tip",
        "Head to the Dream Team Simulator to draft real stars and run 10,000 Monte-Carlo seasons. "
        "Your current roster players are the best starting point — mix a dominant scorer with a "
        "two-way wing for the highest floor.",
        "",
        "*Generated by ReplaysAI · Claude Haiku · ESPN data*",
    ]
    return "\n".join(lines)


@router.post("/generate")
def generate_newsletter(body: NewsletterBody):
    week_key = body.week_key or _current_week_key()
    games = _gather_recent_games(body.favorite_teams)

    content = _build_newsletter_llm(
        body.display_name,
        body.favorite_teams,
        body.followed_players,
        games,
        week_key,
    )
    source = "llm"
    if not content:
        content = _build_newsletter_fallback(
            body.display_name,
            body.favorite_teams,
            body.followed_players,
            games,
            week_key,
        )
        source = "fallback"

    return {
        "user_id": body.user_id,
        "week_key": week_key,
        "content_md": content,
        "teams_snapshot": body.favorite_teams,
        "source": source,
    }


@router.get("/share/{token}")
def get_newsletter_by_token(token: str):
    """Public endpoint — returns a newsletter by its share token.
    The Supabase read happens on the frontend via the anon key; this backend
    endpoint exists as a fallback for non-JS contexts."""
    if not token or len(token) < 8:
        raise HTTPException(status_code=400, detail="Invalid token")
    # The frontend reads directly from Supabase using fetchNewsletterByToken.
    # Return a redirect hint for the frontend to handle.
    return {"token": token, "hint": "read via supabase anon key"}
