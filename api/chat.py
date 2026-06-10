"""Authenticated assistant endpoint backed by the configured LLM."""
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from config import get_settings
from middleware.clerk_auth import AuthUser, get_current_user

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatBody(BaseModel):
    message: str
    context: str | None = None
    favorite_teams: list[str] = Field(default_factory=list)
    messages: list["ChatMessage"] = Field(default_factory=list)


class ChatMessage(BaseModel):
    role: Literal["assistant", "user"]
    text: str


ChatBody.model_rebuild()


def _user_context(user: AuthUser, body: ChatBody) -> str:
    teams = body.favorite_teams[:12]
    players = []
    if body.context:
        teams.append(f"route context: {body.context}")
    return (
        f"User: {user.display_name or user.username or 'fan'}\n"
        f"Favorite teams: {', '.join(teams) if teams else 'none selected'}\n"
        f"Followed players: {', '.join(players[:8]) if players else 'none selected'}"
    )


def _conversation(body: ChatBody) -> list[dict[str, str]]:
    messages = [
        {"role": message.role, "content": message.text}
        for message in body.messages[-12:]
        if message.text.strip()
    ]
    if not messages or messages[-1]["role"] != "user" or messages[-1]["content"] != body.message:
        messages.append({"role": "user", "content": body.message})
    return messages


def _local_reply(body: ChatBody, user: AuthUser) -> str:
    text = body.message.lower()
    context = body.context or "the current page"
    team_hint = ""

    if any(word in text for word in ["recap", "summary", "explain"]):
        return (
            f"I can explain this from {context}{team_hint}. Open a game card and use Recap or Plays; "
            "the app pulls ESPN scoreboard and summary data so the answer is based on the selected matchup."
        )
    if any(word in text for word in ["reel", "video", "highlight", "clip"]):
        return (
            "For reels, start from the Highlights tab. I will use stored CV classifications first, then real ESPN play labels and YouTube highlight search context when available."
        )
    if any(word in text for word in ["pick", "prediction", "who wins", "bet"]):
        return (
            f"My read: compare current score/status, favorite-team context{team_hint}, and recent ESPN play detail before locking a pick. "
            "For scheduled games, pick from the game detail card so it can be scored later."
        )
    if any(word in text for word in ["roster", "player", "fantasy", "draft"]):
        return (
            "Use the roster pool to draft up to 8 players. The player list is backed by stored box scores first and ESPN athlete leaderboards when no local player rows exist."
        )
    return (
        f"I am following the conversation and the current page is {context}. Ask me about a game, player, roster, reel, or prediction and I will ground the answer in your app state."
    )


@router.post("")
def chat(body: ChatBody, user: AuthUser = Depends(get_current_user)):
    settings = get_settings()
    system = (
        "You are ReplaysAI's in-app sports assistant. Help the user understand games, "
        "personalization, reels, fantasy rosters, predictions, and leaderboard strategy. "
        "Use the supplied app context and conversation history. Be conversational, concise, "
        "specific, and action-oriented."
    )
    app_context = f"{_user_context(user, body)}\nCurrent route/context: {body.context or 'none'}"
    conversation = _conversation(body)

    if settings.openai_api_key:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.openai_model,
            max_tokens=450,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": app_context},
                *conversation,
            ],
        )
        return {"reply": (response.choices[0].message.content or "").strip()}

    if settings.anthropic_api_key:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=450,
            system=f"{system}\n\n{app_context}",
            messages=conversation,
        )
        return {"reply": response.content[0].text.strip()}

    return {"reply": _local_reply(body, user)}
