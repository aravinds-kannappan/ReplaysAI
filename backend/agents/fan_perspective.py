"""
Agent 4: Fan Perspective Recap
Takes an existing generic recap + user's favorite team → generates a personalized,
fan-POV narrative. Cached permanently in fan_recaps table.
"""
import asyncio

import anthropic

from backend.config import get_settings
from backend.db.models import FanRecap, Game, GameFeature, Recap, Team
from backend.db.session import get_session_factory

MODEL = "claude-sonnet-4-6"


async def fan_perspective_agent(game_id: int, user_id: int, favorite_team_id: int) -> str:
    SessionLocal = get_session_factory()
    db = SessionLocal()

    try:
        existing = db.query(FanRecap).filter_by(user_id=user_id, game_id=game_id).first()
        if existing and existing.content:
            return existing.content

        game = db.query(Game).get(game_id)
        if not game:
            return ""

        fav_team = db.query(Team).get(favorite_team_id)
        if not fav_team:
            return ""

        generic_recap = db.query(Recap).filter_by(game_id=game_id).first()
        features = db.query(GameFeature).filter_by(game_id=game_id).first()

        home_name = game.home_team.name if game.home_team else "Home"
        away_name = game.away_team.name if game.away_team else "Away"
        home_score = game.home_score or 0
        away_score = game.away_score or 0
        is_home = game.home_team_id == favorite_team_id
        fav_score = home_score if is_home else away_score
        opp_score = away_score if is_home else home_score
        won = fav_score > opp_score

        top_performers_text = ""
        if features and features.top_performers:
            top = features.top_performers[:3]
            top_performers_text = "\n".join([f"- {p['name']}: {p['play_count']} key plays" for p in top])

        generic_text = generic_recap.content if generic_recap and generic_recap.content else "No generic recap available."

        system = (
            f"You are a passionate, knowledgeable sports writer writing EXCLUSIVELY for {fav_team.name} fans. "
            f"Your tone should be {'celebratory and energetic' if won else 'honest, reflective, and forward-looking'}. "
            f"Speak directly to the fan: use 'your team', 'the {fav_team.name}', focus on their players' performances, "
            f"and frame every moment from their perspective."
        )

        prompt = f"""Game: {away_name} @ {home_name}
Final: {fav_team.name} {fav_score} — {'WIN' if won else 'LOSS'} ({opp_score} opponent)

Generic recap for context:
{generic_text[:1500]}

Top performers (all teams):
{top_performers_text or 'Not available'}

Write a 4-paragraph fan-perspective recap for a {fav_team.name} fan:
1. How the game opened for your team
2. The key moment that defined the {'win' if won else 'loss'}
3. Who stepped up (or didn't) for {fav_team.name}
4. {'Celebration + what this means for the season' if won else 'Honest post-mortem + what to watch next game'}

Keep it passionate, specific, and under 350 words."""

        settings = get_settings()
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.messages.create(
                model=MODEL,
                max_tokens=500,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            ),
        )
        content = response.content[0].text.strip()

        existing_entry = db.query(FanRecap).filter_by(user_id=user_id, game_id=game_id).first()
        if existing_entry:
            existing_entry.content = content
            existing_entry.favorite_team_id = favorite_team_id
        else:
            db.add(FanRecap(user_id=user_id, game_id=game_id, favorite_team_id=favorite_team_id, content=content))
        db.commit()

        return content

    finally:
        db.close()
