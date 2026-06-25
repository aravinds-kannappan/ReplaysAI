"""
Reel intent resolution: convert a natural-language prompt into a specific game +
focus + length so the frontend can build a reel in one step, no intermediate
game-selection UI required.
"""
import re

from fastapi import APIRouter
from pydantic import BaseModel

from api.espn_public import fetch_espn_games
from config import get_settings

router = APIRouter(prefix="/api/reels", tags=["reels-intent"])


class IntentBody(BaseModel):
    prompt: str
    favorite_teams: list[str] = []   # list of "SPORT:ABBR" strings
    followed_players: list[str] = []


class IntentResult(BaseModel):
    game_id: int | None
    sport: str | None
    focus: str
    seconds: int
    confidence: float
    game_label: str
    candidates: list[dict]
    intent_source: str


def _candidate_games(favorite_teams: list[str], limit: int = 60) -> list[dict]:
    seen: set[int] = set()
    games: list[dict] = []
    sports = list({t.split(":")[0].upper() for t in favorite_teams if ":" in t}) or ["NBA", "NFL"]
    abbrs = {t.split(":")[1].upper() for t in favorite_teams if ":" in t}

    for sport in sports:
        for g in fetch_espn_games(sport, limit=limit, seasons=3):
            if g.get("id") in seen:
                continue
            if g.get("away_score") is None and g.get("home_score") is None and g.get("status") != "live":
                continue
            h_abbr = (g.get("home_team") or {}).get("abbreviation", "").upper()
            a_abbr = (g.get("away_team") or {}).get("abbreviation", "").upper()
            if abbrs and not (abbrs & {h_abbr, a_abbr}):
                continue
            seen.add(g["id"])
            games.append(g)
    games.sort(key=lambda g: g.get("game_date") or "", reverse=True)
    return games[:40]


def _seconds_from_prompt(prompt: str) -> int:
    text = prompt.lower()
    m = re.search(r"(\d+)\s*-?\s*min", text)
    if m:
        return max(60, min(900, int(m.group(1)) * 60))
    if "quick" in text or "short" in text or "pulse" in text:
        return 120
    if "deep" in text or "full" in text or "detailed" in text:
        return 600
    return 300  # default 5-min story


def _focus_from_prompt(prompt: str) -> str:
    text = prompt.lower()
    if re.search(r"q[1-4]|quarter|half", text):
        for q in ["q4", "q3", "q2", "q1", "4th quarter", "3rd quarter", "2nd quarter", "1st quarter", "fourth quarter", "final quarter", "second half", "first half"]:
            if q in text:
                return q
    if "dunk" in text:
        return "dunks"
    if "three" in text or "3-point" in text or "3pt" in text:
        return "three-pointers"
    if "block" in text or "steal" in text:
        return "defensive plays"
    if "foul" in text:
        return "fouls"
    return "whole game"


def _llm_resolve(prompt: str, favorite_teams: list[str], followed_players: list[str], candidates: list[dict]) -> dict | None:
    settings = get_settings()
    if not settings.anthropic_api_key or not candidates:
        return None

    catalog_lines = []
    for i, g in enumerate(candidates[:20]):
        ht = (g.get("home_team") or {}).get("abbreviation", "?")
        at = (g.get("away_team") or {}).get("abbreviation", "?")
        hs = g.get("home_score")
        as_ = g.get("away_score")
        date = (g.get("game_date") or "")[:10]
        score = f"{as_}-{hs}" if as_ is not None else "scheduled"
        catalog_lines.append(f"{i}: {at} @ {ht} ({score}) {date} id={g['id']}")
    catalog = "\n".join(catalog_lines)

    teams_str = ", ".join(favorite_teams) or "none"
    players_str = ", ".join(followed_players[:8]) or "none"

    system = (
        "You are ReplaysAI's reel intent resolver. Given a fan's natural-language reel request "
        "and a catalog of available games, identify which game best matches the request and extract "
        "the reel focus and length.\n\n"
        "Respond ONLY with JSON:\n"
        '{"game_index": 0, "focus": "whole game", "seconds": 300, "confidence": 0.85}\n\n'
        "game_index: index into the catalog (0-based). -1 if no match.\n"
        "focus: what the reel should focus on (player name, quarter, play type, or 'whole game').\n"
        "seconds: 120 (2-min), 300 (5-min), or 600 (10-min).\n"
        "confidence: 0.0 to 1.0."
    )
    msg = (
        f"Fan request: {prompt}\n\n"
        f"Favorite teams: {teams_str}\nFollowed players: {players_str}\n\n"
        f"Available games:\n{catalog}"
    )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        raw = ""
        for model in settings.anthropic_models:
            try:
                resp = client.messages.create(
                    model=model,
                    max_tokens=200,
                    system=system,
                    messages=[{"role": "user", "content": msg}],
                )
                raw = resp.content[0].text.strip()
                break
            except Exception as exc:
                print(f"[reel-intent] {model}: {exc}")
        if not raw:
            return None
        import json as _json
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None
        parsed = _json.loads(m.group(0))
        idx = int(parsed.get("game_index", -1))
        if idx < 0 or idx >= len(candidates):
            return None
        game = candidates[idx]
        ht = (game.get("home_team") or {}).get("abbreviation", "?")
        at = (game.get("away_team") or {}).get("abbreviation", "?")
        hs = game.get("home_score")
        as_ = game.get("away_score")
        score = f"{as_}-{hs}" if as_ is not None else ""
        label = f"{at} @ {ht}{' ' + score if score else ''}"
        return {
            "game_id": game["id"],
            "sport": game.get("sport"),
            "focus": str(parsed.get("focus") or "whole game"),
            "seconds": int(parsed.get("seconds") or 300),
            "confidence": float(parsed.get("confidence") or 0.7),
            "game_label": label,
        }
    except Exception as exc:
        print(f"[reel-intent] LLM failed: {exc}")
        return None


@router.post("/intent", response_model=IntentResult)
def resolve_reel_intent(body: IntentBody) -> IntentResult:
    """Convert a natural language reel request into a resolved game + focus."""
    candidates = _candidate_games(body.favorite_teams)

    # Try LLM first
    llm_result = _llm_resolve(body.prompt, body.favorite_teams, body.followed_players, candidates)
    if llm_result:
        return IntentResult(
            **llm_result,
            candidates=[
                {"id": g["id"], "label": f"{(g.get('away_team') or {}).get('abbreviation','?')} @ {(g.get('home_team') or {}).get('abbreviation','?')}",
                 "date": (g.get("game_date") or "")[:10], "score": f"{g.get('away_score','—')}-{g.get('home_score','—')}"}
                for g in candidates[:5]
            ],
            intent_source="llm",
        )

    # Keyword fallback: pick most recent game, extract focus and seconds from prompt
    seconds = _seconds_from_prompt(body.prompt)
    focus = _focus_from_prompt(body.prompt)
    game = candidates[0] if candidates else None
    if game:
        ht = (game.get("home_team") or {}).get("abbreviation", "?")
        at = (game.get("away_team") or {}).get("abbreviation", "?")
        hs = game.get("home_score")
        as_ = game.get("away_score")
        score = f"{as_}-{hs}" if as_ is not None else ""
        label = f"{at} @ {ht}{' ' + score if score else ''} (most recent)"
    else:
        label = "no game found"

    return IntentResult(
        game_id=game["id"] if game else None,
        sport=game.get("sport") if game else None,
        focus=focus,
        seconds=seconds,
        confidence=0.5 if game else 0.0,
        game_label=label,
        candidates=[
            {"id": g["id"], "label": f"{(g.get('away_team') or {}).get('abbreviation','?')} @ {(g.get('home_team') or {}).get('abbreviation','?')}",
             "date": (g.get("game_date") or "")[:10], "score": f"{g.get('away_score','—')}-{g.get('home_score','—')}"}
            for g in candidates[:5]
        ],
        intent_source="fallback",
    )
