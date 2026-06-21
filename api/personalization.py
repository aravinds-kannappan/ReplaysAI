"""Personalized feed generation orchestration.

This endpoint is intentionally slower than a normal data fetch. It represents
the moment after a fan picks teams and star players, when the backend runs the
specialist Anthropic agents before the dashboard opens.
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from config import get_settings

router = APIRouter(prefix="/api/personalization", tags=["personalization"])


class PersonalizationBody(BaseModel):
    teams: list[dict[str, Any]] = Field(default_factory=list)
    players: list[dict[str, Any]] = Field(default_factory=list)
    min_seconds: int = 32


AGENT_TASKS = [
    ("Personalization", "Build the fan graph and explain what the feed should prioritize."),
    ("Stats", "Identify the statistical context needed for the selected teams and players."),
    ("Prediction", "Describe the model signals to use for picks and season outlook."),
    ("Reel Director", "Define the reel strategy and voiceover style for 2, 5, and 10 minute cuts."),
    ("Fan Voice", "Define how recaps should adapt to wins, losses, and fan perspective."),
]


def _anthropic_agent(agent: str, task: str, teams: list[dict], players: list[dict]) -> str:
    settings = get_settings()
    if not settings.anthropic_api_key:
        return "Anthropic key missing; generated feed will use deterministic ESPN-data fallbacks."

    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    team_lines = ", ".join(f"{t.get('sport')}:{t.get('abbreviation')} {t.get('name')}" for t in teams) or "none"
    player_lines = ", ".join(f"{p.get('sport')}:{p.get('name')} ({p.get('team')})" for p in players) or "none"
    system = (
        f"You are ReplaysAI's {agent} Agent. You are one specialist in a multi-agent sports fan "
        "platform. Be detailed, concrete, and grounded in the selected teams and players. "
        "Do not invent unavailable statistics; describe what data must be retrieved and how it "
        "should shape the personalized feed."
    )
    prompt = (
        f"Task: {task}\n\nSelected teams: {team_lines}\nSelected star players: {player_lines}\n\n"
        "Return a concise but specific agent handoff for the dashboard generation pipeline."
    )
    last_error = ""
    for model in settings.anthropic_models:
        try:
            response = client.messages.create(
                model=model,
                max_tokens=500,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception as exc:
            last_error = f"{model}: {type(exc).__name__}: {str(exc)[:180]}"
    return f"Anthropic call failed: {last_error}"


@router.post("/generate")
def generate_personalized_feed(body: PersonalizationBody):
    start = time.monotonic()
    min_seconds = max(30, min(60, body.min_seconds))
    outputs = [
        {"agent": name, "content": _anthropic_agent(name, task, body.teams, body.players)}
        for name, task in AGENT_TASKS
    ]
    remaining = min_seconds - (time.monotonic() - start)
    if remaining > 0:
        time.sleep(remaining)
    return {
        "status": "ready",
        "provider": "anthropic" if get_settings().anthropic_api_key else "fallback",
        "elapsed_seconds": round(time.monotonic() - start, 1),
        "outputs": outputs,
    }
