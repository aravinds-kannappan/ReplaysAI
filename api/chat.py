"""Authenticated assistant endpoint backed by the configured LLM."""
import threading
import time
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from config import get_settings
from middleware.clerk_auth import AuthUser, get_current_user

router = APIRouter(prefix="/api/chat", tags=["chat"])

_health_lock = threading.Lock()
_health_cache: tuple[float, dict] | None = None


@router.get("/health")
def chat_health():
    """Cheap diagnostic: is the configured LLM provider actually reachable?
    Result is cached in-process for 10 minutes; the probe costs ~1 output token."""
    global _health_cache
    with _health_lock:
        if _health_cache and time.monotonic() - _health_cache[0] < 600:
            return _health_cache[1]

    settings = get_settings()
    if settings.anthropic_api_key:
        provider, model = "anthropic", settings.anthropic_model
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            errors = []
            for model in settings.anthropic_models:
                try:
                    client.messages.create(
                        model=model,
                        max_tokens=1,
                        messages=[{"role": "user", "content": "ping"}],
                    )
                    result = {
                        "ok": True,
                        "provider": provider,
                        "model": model,
                        "key_present": True,
                        "fallback_models": settings.anthropic_models[1:],
                    }
                    break
                except Exception as exc:
                    errors.append(f"{model}: {type(exc).__name__}: {str(exc)[:180]}")
            else:
                result = {
                    "ok": False,
                    "provider": provider,
                    "model": model,
                    "key_present": True,
                    "fallback_models": settings.anthropic_models[1:],
                    "detail": " | ".join(errors)[:500],
                }
        except Exception as exc:
            result = {"ok": False, "provider": provider, "model": model, "key_present": True, "detail": str(exc)[:300]}
    elif settings.openai_api_key:
        provider, model = "openai", settings.openai_model
        try:
            from openai import OpenAI

            OpenAI(api_key=settings.openai_api_key).chat.completions.create(
                model=model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            result = {"ok": True, "provider": provider, "model": model, "key_present": True}
        except Exception as exc:
            result = {"ok": False, "provider": provider, "model": model, "key_present": True, "detail": str(exc)[:300]}
    else:
        result = {"ok": False, "provider": None, "model": None, "key_present": False, "detail": "No LLM API key configured in this environment"}

    with _health_lock:
        _health_cache = (time.monotonic(), result)
    return result


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
            "I will focus on the score flow, turning points, player production, and what changed the game."
        )
    if any(word in text for word in ["reel", "video", "highlight", "clip"]):
        return (
            "For reels, open the Reels tab on a game or the main Reels studio. Tell me the focus and length, then I will build a generated story reel instead of sending you to a video link."
        )
    if any(word in text for word in ["pick", "prediction", "who wins", "bet"]):
        return (
            f"My read: compare current score/status, favorite-team context{team_hint}, and recent play detail before locking a pick. "
            "For scheduled games, pick from the game detail card so it can be scored later."
        )
    if any(word in text for word in ["roster", "player", "fantasy", "draft"]):
        return (
            "Use the roster pool to draft up to 8 players. The player list is backed by stored box scores first and ESPN athlete leaderboards when no local player rows exist."
        )
    return (
        f"I am following the conversation and the current page is {context}. Ask me about a game, player, roster, reel, or prediction and I will ground the answer in your app state."
    )


def _llm_reply(system: str, app_context: str, conversation: list[dict[str, str]]) -> tuple[str, str] | None:
    """Try each configured provider; return (reply, source) or None so the
    endpoint can degrade to the local reply instead of returning a 500."""
    settings = get_settings()

    if settings.anthropic_api_key:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            for model in settings.anthropic_models:
                try:
                    response = client.messages.create(
                        model=model,
                        max_tokens=700,
                        system=f"{system}\n\n{app_context}",
                        messages=conversation,
                    )
                    return response.content[0].text.strip(), f"anthropic:{model}"
                except Exception as exc:
                    print(f"[chat] Anthropic call failed ({model}): {exc}")
        except Exception as exc:
            print(f"[chat] Anthropic client failed: {exc}")

    if settings.openai_api_key:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key)
            response = client.chat.completions.create(
                model=settings.openai_model,
                max_tokens=700,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": app_context},
                    *conversation,
                ],
            )
            return (response.choices[0].message.content or "").strip(), "openai"
        except Exception as exc:
            print(f"[chat] OpenAI call failed ({settings.openai_model}): {exc}")

    return None


@router.post("")
def chat(body: ChatBody, user: AuthUser = Depends(get_current_user)):
    system = (
        "You are ReplaysAI's in-app sports assistant. Help the user understand games, "
        "personalization, reels, fantasy rosters, predictions, and leaderboard strategy. "
        "Use the supplied app context and conversation history. Be conversational, concise, "
        "specific, and action-oriented."
    )
    app_context = f"{_user_context(user, body)}\nCurrent route/context: {body.context or 'none'}"
    conversation = _conversation(body)

    result = _llm_reply(system, app_context, conversation)
    if result is not None:
        reply, source = result
        return {"reply": reply, "source": source}
    return {"reply": _local_reply(body, user), "source": "fallback"}
