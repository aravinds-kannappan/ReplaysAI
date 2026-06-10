"""
Agent 3: Task-Split LLM Summarization
Breaks a game recap into 4 parallel LLM calls, then assembles the narrative.
Each sub-task is a separate Claude Sonnet call run concurrently via asyncio.gather().
"""
import asyncio
from typing import Optional

import anthropic

from config import get_settings
from db.models import Game, Play, Recap
from db.session import get_session_factory

MAX_PLAYS_PER_TASK = 80


def _format_plays_for_prompt(plays: list[Play], start_period: int, end_period: int) -> str:
    filtered = [p for p in plays if start_period <= (p.period or 0) <= end_period]
    lines = []
    for p in filtered[:MAX_PLAYS_PER_TASK]:
        score = f"({p.away_score}-{p.home_score})" if p.home_score is not None else ""
        lines.append(f"Q{p.period} {p.clock}: {p.description} {score}")
    return "\n".join(lines) if lines else "No play data available."


async def _run_task(client: anthropic.Anthropic, model: str, system: str, prompt: str) -> str:
    loop = asyncio.get_event_loop()
    try:
        response = await loop.run_in_executor(
            None,
            lambda: client.messages.create(
                model=model,
                max_tokens=600,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            ),
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"[LLM] Task failed: {e}")
        return ""


async def llm_summarization_agent(game_id: int, features: Optional[dict] = None, cv_results: Optional[list] = None) -> str:
    SessionLocal = get_session_factory()
    db = SessionLocal()

    try:
        existing = db.query(Recap).filter_by(game_id=game_id).first()
        if existing and existing.content:
            return existing.content

        game = db.query(Game).get(game_id)
        if not game:
            return ""

        home_name = game.home_team.name if game.home_team else "Home Team"
        away_name = game.away_team.name if game.away_team else "Away Team"
        home_score = game.home_score or 0
        away_score = game.away_score or 0
        sport = game.sport or "NBA"
        date_str = game.game_date.strftime("%B %d, %Y") if game.game_date else "recent game"

        plays = db.query(Play).filter_by(game_id=game_id).order_by(Play.id).all()

        system = (
            f"You are a sports writer generating a vivid, engaging game recap for a {sport} game. "
            f"Write in present tense, with energy and narrative flow. Be concise but compelling."
        )

        game_context = (
            f"Game: {away_name} @ {home_name} on {date_str}\n"
            f"Final Score: {away_name} {away_score} — {home_name} {home_score}\n"
        )

        first_half_plays = _format_plays_for_prompt(plays, 1, 2)
        second_half_plays = _format_plays_for_prompt(plays, 3, 4)

        top_performers_text = ""
        if features and features.get("top_performers"):
            perf_lines = [f"- {p['name']} ({p['play_count']} key plays)" for p in features["top_performers"][:3]]
            top_performers_text = "\n".join(perf_lines)

        key_moments_text = ""
        if features and features.get("key_moments"):
            moment_lines = [f"- {m['description']}" for m in features["key_moments"][:5] if m.get("description")]
            key_moments_text = "\n".join(moment_lines)

        highlight_plays_text = ""
        if cv_results:
            exciting = [r for r in cv_results if r["play_type"] in ("dunk", "block", "steal", "touchdown", "interception") and r["confidence"] > 0.6]
            if exciting:
                highlight_plays_text = f"{len(exciting)} highlight plays detected: " + ", ".join(set(r["play_type"] for r in exciting))

        # 4 parallel sub-tasks
        task1_prompt = (
            f"{game_context}\n\nFirst half plays:\n{first_half_plays}\n\n"
            f"Write a 2-3 sentence recap of the first half. Focus on how the game opened and any early momentum."
        )
        task2_prompt = (
            f"{game_context}\n\nSecond half / final stretch plays:\n{second_half_plays}\n\n"
            f"Write a 2-3 sentence recap of the second half and finish. Capture the drama and final result."
        )
        task3_prompt = (
            f"{game_context}\n\nTop performers:\n{top_performers_text or 'Not available'}\n\n"
            f"Write a 2-sentence player spotlight on the standout performer(s). Be specific about their impact."
        )
        task4_prompt = (
            f"{game_context}\n\nKey clutch moments:\n{key_moments_text or 'Not available'}\n"
            f"Visual highlights detected: {highlight_plays_text or 'None'}\n\n"
            f"Write 2 sentences on the single most decisive moment of the game."
        )

        settings = get_settings()
        if settings.anthropic_api_key:
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

            print(f"[LLM] Running 4 parallel summarization tasks for game {game_id}...")
            first_half, second_half, player_spotlight, key_play = await asyncio.gather(
                _run_task(client, settings.anthropic_model, system, task1_prompt),
                _run_task(client, settings.anthropic_model, system, task2_prompt),
                _run_task(client, settings.anthropic_model, system, task3_prompt),
                _run_task(client, settings.anthropic_model, system, task4_prompt),
            )
            model_version = settings.anthropic_model
        else:
            first_half = " ".join(p.description for p in plays if (p.period or 0) <= 2 and p.description)[:700] or "Early play-by-play has not been published yet."
            second_half = " ".join(p.description for p in plays if (p.period or 0) >= 3 and p.description)[:700] or "Late-game play-by-play has not been published yet."
            player_spotlight = top_performers_text or "Player impact will become clearer once box score and play data fill in."
            key_play = key_moments_text or highlight_plays_text or "The defining moment will update as key plays are classified."
            model_version = "local-template"

        winner = home_name if home_score > away_score else away_name
        loser = away_name if home_score > away_score else home_name
        winner_score = max(home_score, away_score)
        loser_score = min(home_score, away_score)

        full_recap = f"""# {away_name} vs. {home_name} — {date_str}
**Final: {away_name} {away_score}, {home_name} {home_score}**

## First Half
{first_half}

## Second Half & Finish
{second_half}

## Player Spotlight
{player_spotlight}

## Defining Moment
{key_play}

---
*{winner} defeat {loser} {winner_score}–{loser_score}.*"""

        existing_recap = db.query(Recap).filter_by(game_id=game_id).first()
        if existing_recap:
            existing_recap.content = full_recap
            existing_recap.model_version = model_version
        else:
            recap = Recap(game_id=game_id, content=full_recap, model_version=model_version)
            db.add(recap)
        db.commit()

        print(f"[LLM] Recap saved for game {game_id}")
        return full_recap

    finally:
        db.close()
