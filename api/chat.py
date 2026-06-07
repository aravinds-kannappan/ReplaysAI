"""Authenticated assistant endpoint backed by the configured LLM."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from config import get_settings
from db.models import User
from middleware.clerk_auth import get_current_user

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatBody(BaseModel):
    message: str
    context: str | None = None


@router.post("")
def chat(body: ChatBody, user: User = Depends(get_current_user)):
    settings = get_settings()
    if not settings.anthropic_api_key:
        return {
            "reply": (
                "I need ANTHROPIC_API_KEY configured on the backend to answer dynamically. "
                "Once it is set in Vercel, I can reason over teams, reels, picks, rosters, and leaders."
            )
        }

    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=450,
        system=(
            "You are ReplaysAI's in-app sports assistant. Help the user understand games, "
            "personalization, reels, fantasy rosters, predictions, and leaderboard strategy. "
            "Be conversational, concise, and action-oriented."
        ),
        messages=[{
            "role": "user",
            "content": f"User: {user.display_name or user.username or 'fan'}\nContext: {body.context or 'none'}\nQuestion: {body.message}",
        }],
    )
    return {"reply": response.content[0].text.strip()}
