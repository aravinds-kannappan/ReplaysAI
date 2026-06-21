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
    followed_players: list[str] = Field(default_factory=list)
    messages: list["ChatMessage"] = Field(default_factory=list)


class ChatMessage(BaseModel):
    role: Literal["assistant", "user"]
    text: str


ChatBody.model_rebuild()


def _user_context(user: AuthUser, body: ChatBody) -> str:
    teams = body.favorite_teams[:12]
    players = body.followed_players[:12]
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
    teams = ", ".join(body.favorite_teams[:8]) or "your selected teams"
    players = ", ".join(body.followed_players[:8]) or "your followed players"

    if any(word in text for word in ["recap", "summary", "explain"]):
        return (
            f"Here is how I would handle the recap from {context}: start with the final score and score flow, "
            f"then isolate the decisive run or possession swing, then connect star production for {players} "
            f"back to {teams}. Open a game card and use Recap, My Team, Reels, or Plays for the fully grounded version."
        )
    if any(word in text for word in ["reel", "video", "highlight", "clip"]):
        return (
            "For reels, I work like a reel director: choose a game, then tell me the focus and tier. "
            "Tier 1 is a 2-minute quick rundown, Tier 2 is a 5-minute detailed recap, and Tier 3 is a 10-minute deep dive. "
            "You can narrow it by player, quarter, play type, or the whole game."
        )
    if any(word in text for word in ["pick", "prediction", "who wins", "bet"]):
        return (
            f"My prediction workflow compares recent form, scoring edge, live status, and favorite-team context for {teams}. "
            "I would avoid treating it as betting advice; use it as a model-style confidence read before locking a pick."
        )
    if any(word in text for word in ["roster", "player", "fantasy", "draft"]):
        return (
            f"For roster strategy, I rank ceiling, role stability, and matchup context for {players}. "
            "Draft up to 8 players, then use the stats and leaders panels to compare production and risk."
        )
    return (
        f"I am following the conversation from {context}. I can answer as the Stats Agent, Prediction Agent, "
        f"Reel Director Agent, Fan Voice Agent, News Agent, or Roster Agent for {teams} and {players}. "
        "Ask for a detailed breakdown when you want a deeper brief."
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
                        max_tokens=1400,
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
                max_tokens=1400,
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
        "You are ReplaysAI's in-app sports assistant and coordinator for six specialist agents: "
        "Personalization Agent, Stats Agent, Prediction Agent, Reel Director Agent, Fan Voice Agent, "
        "and News/Roster Agent. Help the user understand games, personalization, reels, fantasy "
        "rosters, predictions, leaderboards, and fan-perspective recaps. Use the supplied app "
        "context and conversation history. Be specific and detailed when asked: name the agent "
        "perspective you are using, cite the exact dashboard context you were given, separate facts "
        "from model-style inference, and never invent unavailable stats, clips, or scores.\n\n"
        "INTERRUPT-AND-ASK: if the context begins with 'reel ' it is a paused highlight reel. The "
        "viewer stopped on a specific clip — answer their question about THAT moment first, grounding "
        "your reply in the supplied segment/clip and recentNarration. As the in-reel analyst you may "
        "draw on the rulebook, box score, and historical comparables that are relevant. Keep it tight "
        "and broadcast-toned (a few sentences) so playback can resume; cite the clip/timestamp you "
        "were given and never fabricate plays or numbers."
    )
    app_context = f"{_user_context(user, body)}\nCurrent route/context: {body.context or 'none'}"
    conversation = _conversation(body)

    result = _llm_reply(system, app_context, conversation)
    if result is not None:
        reply, source = result
        return {"reply": reply, "source": source}
    return {"reply": _local_reply(body, user), "source": "fallback"}
