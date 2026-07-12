"""
Personalized weekly newsletter generator.

Curated by the learned ranker (api/curation.py) and written by the newsletter
agent (trained model, then LLM, then a deterministic template). Each generated
issue is saved to the store by share token so its public link resolves. The
content is a Markdown document with publication-style sections.
"""
from __future__ import annotations

import secrets
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.espn_public import fetch_espn_games, fetch_espn_team_schedule, fetch_espn_teams
from api.recaps import llm_text, trained_text
from api import curation
from config import get_settings
from db import store

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

    def _consider(g: dict) -> None:
        if g.get("id") in seen or g.get("away_score") is None:
            return
        seen.add(g["id"])
        games.append(g)

    # Pull each followed team's own schedule so the digest always has their real
    # recent results, even when they aren't in the league-wide recent window
    # (e.g. eliminated from the playoffs).
    if abbrs:
        for sport in sports:
            try:
                team_ids = {t["abbreviation"].upper(): t["id"] for t in fetch_espn_teams(sport)}
            except Exception:
                team_ids = {}
            for abbr in abbrs:
                team_id = team_ids.get(abbr)
                if team_id is not None:
                    for g in fetch_espn_team_schedule(sport, team_id):
                        _consider(g)

    for sport in sports:
        for g in fetch_espn_games(sport, limit=40, seasons=1):
            h = (g.get("home_team") or {}).get("abbreviation", "").upper()
            a = (g.get("away_team") or {}).get("abbreviation", "").upper()
            if abbrs and not (abbrs & {h, a}):
                continue
            _consider(g)
    games.sort(key=lambda g: g.get("game_date") or "", reverse=True)
    return games[:12]


def _rank_games(favorite_teams: list[str], games: list[dict]) -> list[dict]:
    """Order games by the learned curation ranker so the writer leads with the
    stories that matter most to this fan (their teams, recent, high drama)."""
    abbrs = {t.split(":")[1].upper() for t in favorite_teams if ":" in t}
    today = date.today()
    items = []
    for g in games:
        h = (g.get("home_team") or {}).get("abbreviation", "").upper()
        a = (g.get("away_team") or {}).get("abbreviation", "").upper()
        gd = (g.get("game_date") or "")[:10]
        try:
            recency = (today - date.fromisoformat(gd)).days if gd else 7
        except ValueError:
            recency = 7
        margin = abs((g.get("home_score") or 0) - (g.get("away_score") or 0))
        magnitude = 1.0 if margin <= 3 else 0.8 if margin <= 8 else 0.55
        items.append({
            "followed_team": bool(abbrs & {h, a}),
            "recency_days": max(0, recency),
            "magnitude": magnitude,
            "upcoming": g.get("status") == "scheduled",
            "game": g,
        })
    return [it["game"] for it in curation.rank_items(items)]


def _newsletter_prompt(
    display_name: str | None,
    favorite_teams: list[str],
    followed_players: list[str],
    games: list[dict],
    week_key: str,
) -> tuple[str, str]:
    """The (system, prompt) shared by the trained writer, the LLM fallback, and
    the offline teacher (training/distill.py), so train and serve match exactly.
    Games are ordered by the curation ranker before they reach the writer."""
    ranked = _rank_games(favorite_teams, games)
    team_names = ", ".join(favorite_teams) or "no specific teams"
    player_names = ", ".join(followed_players[:10]) or "no specific players"
    fan_name = display_name or "Fan"

    game_lines: list[str] = []
    for g in ranked[:10]:
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
        "for this fan. Write in a confident, engaging magazine voice: specific, analytical, with "
        "personality. Use only the data provided; never invent stats, results, or injuries. "
        "The games are pre-ranked by relevance to this fan, so lead with the earliest ones.\n\n"
        "Format as Markdown with these EXACT sections:\n"
        "## Week in Review\n"
        "## Your Players This Week\n"
        "## Games to Watch\n"
        "## The Take\n\n"
        "Aim for 450-650 words total. Make it feel personal to this fan's teams and players."
    )
    prompt = (
        f"Fan: {fan_name}\n"
        f"Teams followed: {team_names}\n"
        f"Players followed: {player_names}\n"
        f"Week: {week_key}\n\n"
        f"Games (most relevant first):\n{games_block}\n\n"
        "Write the newsletter."
    )
    return system, prompt


def _write_newsletter(
    display_name: str | None,
    favorite_teams: list[str],
    followed_players: list[str],
    games: list[dict],
    week_key: str,
) -> tuple[str | None, str | None]:
    """Write the digest. The trained writer produces the prose (falling back to
    the general LLM). Returns (markdown, source) where source is "trained" or
    "llm", or (None, None) when no model is set."""
    settings = get_settings()
    system, prompt = _newsletter_prompt(display_name, favorite_teams, followed_players, games, week_key)

    text = trained_text(system=system, prompt=prompt, model=settings.newsletter_model, max_tokens=1400)
    if text:
        return text, "trained"
    text = llm_text(system=system, prompt=prompt, max_tokens=1400)
    if text:
        return text, "llm"
    return None, None


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
        f"# ReplaysAI Weekly: {week_key}",
        f"*Your personalized sports digest, {fan_name}.*",
        "",
        "## Week in Review",
    ]
    if games:
        for g in games[:5]:
            ht = (g.get("home_team") or {}).get("name", "?")
            at = (g.get("away_team") or {}).get("name", "?")
            hs = g.get("home_score", "-")
            as_ = g.get("away_score", "-")
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
        f"Based on recent results, your teams are in the mix. The season is long, and one week can shift "
        "the narrative completely. Keep an eye on the Prediction desk for model reads before each game.",
        "",
        "*Generated by ReplaysAI from real ESPN data (deterministic fallback).*",
    ]
    return "\n".join(lines)


@router.post("/generate")
def generate_newsletter(body: NewsletterBody):
    week_key = body.week_key or _current_week_key()
    games = _gather_recent_games(body.favorite_teams)

    content, source = _write_newsletter(
        body.display_name,
        body.favorite_teams,
        body.followed_players,
        games,
        week_key,
    )
    if not content:
        content = _build_newsletter_fallback(
            body.display_name,
            body.favorite_teams,
            body.followed_players,
            games,
            week_key,
        )
        source = "fallback"

    share_token = secrets.token_urlsafe(9)
    payload = {
        "user_id": body.user_id,
        "week_key": week_key,
        "content_md": content,
        "teams_snapshot": body.favorite_teams,
        "source": source,           # "trained" | "llm" | "fallback"
        "curation": curation.model_label(),
        "share_token": share_token,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    # Persist so the public /share link resolves. Best effort: a missing store
    # never blocks the digest from rendering, the share link just won't resolve.
    store.save_newsletter(share_token, payload)
    return payload


@router.get("/share/{token}")
def get_newsletter_by_token(token: str):
    """Public endpoint: return a shared newsletter by its token."""
    if not token or len(token) < 8:
        raise HTTPException(status_code=400, detail="Invalid token")
    newsletter = store.get_newsletter(token)
    if not newsletter:
        raise HTTPException(status_code=404, detail="Newsletter not found or link expired")
    return newsletter
