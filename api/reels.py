import json
import re
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.espn_public import (
    extract_summary_highlights,
    extract_summary_plays,
    extract_summary_videos,
    fetch_espn_game_by_id,
    fetch_espn_summary_by_id,
)
from config import get_settings

router = APIRouter(prefix="/api/games", tags=["reels"])

CUT_LENGTHS = [120, 300, 600]


def _resolve_game(game_id: int) -> tuple[str, dict, dict]:
    resolved_game = fetch_espn_game_by_id(game_id)
    resolved_summary = fetch_espn_summary_by_id(game_id)
    if not resolved_game or not resolved_summary:
        raise HTTPException(status_code=404, detail="Game not found")
    sport, game_data = resolved_game
    _, summary = resolved_summary
    return sport, game_data, summary


def _segment_weight(play_type: str) -> int:
    weights = {
        "touchdown": 10,
        "dunk": 9,
        "three_pointer": 8,
        "interception": 8,
        "sack": 7,
        "block": 7,
        "steal": 7,
        "field_goal": 6,
        "turnover": 6,
        "assist": 5,
        "shot": 4,
    }
    return weights.get(play_type, 1)


def _build_segments(plays: list[dict], highlights: list[dict]) -> list[dict]:
    highlight_types = {highlight["play_type"] for highlight in highlights}
    segments = []
    for index, play in enumerate(plays):
        play_type = play.get("play_type") or "other"
        if play_type == "other" and play_type not in highlight_types:
            continue
        segments.append({
            "timestamp": float(index * 35),
            "duration": 18,
            "period": play.get("period"),
            "clock": play.get("clock"),
            "play_type": play_type,
            "description": play.get("description"),
            "score": {
                "away": play.get("away_score"),
                "home": play.get("home_score"),
            },
            "weight": _segment_weight(play_type),
        })
    return sorted(segments, key=lambda item: (-item["weight"], item["timestamp"]))[:40]


def _fill_budget(clips: list[dict], budget_seconds: int) -> tuple[list[dict], int]:
    """Greedy playlist fill: keep ESPN's order, skip clips that overshoot."""
    selected: list[dict] = []
    running = 0
    for clip in clips:
        duration = clip.get("duration") or 30
        if running + duration > budget_seconds and selected:
            continue
        selected.append(clip)
        running += duration
        if running >= budget_seconds:
            break
    return selected, running


def _segments_for_length(segments: list[dict], length: int) -> tuple[list[dict], int]:
    running = 0
    selected = []
    for segment in segments:
        if running + segment["duration"] > length and selected:
            continue
        selected.append({key: value for key, value in segment.items() if key != "weight"})
        running += segment["duration"]
        if running >= length:
            break
    return selected, running


def _cuts_from_sources(clips: list[dict], segments: list[dict]) -> list[dict]:
    cuts = []
    for length in CUT_LENGTHS:
        cut_clips, clip_seconds = _fill_budget(clips, length)
        cut_segments, segment_seconds = _segments_for_length(segments, length)
        cuts.append({
            "duration_seconds": length,
            "label": f"{length // 60} min cut",
            "clips": cut_clips,
            "segments": cut_segments,
            "estimated_seconds": clip_seconds if cut_clips else segment_seconds,
            "status": "ready" if (cut_clips or cut_segments) else "no_segments",
        })
    return cuts


@router.get("/{game_id}/reels")
def get_reel_cuts(game_id: int):
    sport, game_data, summary = _resolve_game(game_id)
    plays = extract_summary_plays(summary, sport, limit=500)
    highlights = extract_summary_highlights(summary, sport)
    clips = extract_summary_videos(summary)
    segments = _build_segments(plays, highlights)
    return {
        "game_id": game_id,
        "clip_count": len(clips),
        "cuts": _cuts_from_sources(clips, segments),
        "rendering": {
            "mp4_available": False,
            "playback": "clip_playlist" if clips else "manifest_only",
            "reason": (
                "Cuts play as ordered ESPN highlight clips streamed from ESPN's CDN."
                if clips
                else "ESPN has not published video clips for this game yet; cuts fall back to timestamped play manifests."
            ),
        },
    }


class ReelTurn(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class ReelRequest(BaseModel):
    prompt: str
    max_seconds: int | None = None
    messages: list[ReelTurn] = Field(default_factory=list)


_STOPWORDS = {
    "the", "and", "for", "with", "from", "all", "any", "give", "show", "make",
    "build", "create", "generate", "want", "reel", "reels", "video", "videos",
    "clip", "clips", "highlight", "highlights", "play", "plays", "moments",
    "minute", "minutes", "min", "second", "seconds", "sec", "long", "short",
    "please", "that", "this", "game", "best", "top", "every", "just", "only",
}


def _budget_from_prompt(prompt: str) -> int | None:
    minutes = re.search(r"(\d+)\s*-?\s*min", prompt.lower())
    if minutes:
        return max(30, min(900, int(minutes.group(1)) * 60))
    seconds = re.search(r"(\d+)\s*-?\s*sec", prompt.lower())
    if seconds:
        return max(30, min(900, int(seconds.group(1))))
    return None


def _token_matches(token: str, haystack_words: list[str]) -> bool:
    # Shared 4+ char prefix catches nickname/inflection pairs the captions use,
    # e.g. "Wembanyama" vs "Wemby", "Brunson" vs "Brunson's".
    for word in haystack_words:
        if token in word or word in token:
            return True
        if len(token) >= 4 and len(word) >= 4 and token[:4] == word[:4]:
            return True
    return False


def _select_clips_keywords(prompt: str, clips: list[dict], budget: int) -> tuple[list[dict], str]:
    tokens = [
        token for token in re.findall(r"[a-z0-9']+", prompt.lower())
        if len(token) > 2 and token not in _STOPWORDS
    ]
    scored = []
    for index, clip in enumerate(clips):
        haystack_words = re.findall(r"[a-z0-9']+", f"{clip['headline']} {clip['description']}".lower())
        score = sum(1 for token in tokens if _token_matches(token, haystack_words))
        if score > 0:
            scored.append((score, index, clip))

    if scored:
        scored.sort(key=lambda item: (-item[0], item[1]))
        ranked = [clip for _, _, clip in scored]
        selected, running = _fill_budget(ranked, budget)
        note = f"Matched {len(selected)} ESPN clips ({running}s) for your request."
    else:
        selected, running = _fill_budget(clips, budget)
        note = (
            "No clip captions matched those words, so this reel uses the top plays "
            f"of the game instead ({running}s)."
        )
    return selected, note


def _agent_turns(body: ReelRequest) -> list[dict[str, str]]:
    turns = [
        {"role": turn.role, "content": turn.text}
        for turn in body.messages[-10:]
        if turn.text.strip()
    ]
    if not turns or turns[-1]["role"] != "user" or turns[-1]["content"] != body.prompt:
        turns.append({"role": "user", "content": body.prompt})
    return turns


def _reel_agent_llm(body: ReelRequest, clips: list[dict], budget: int) -> dict | None:
    """Conversational director: either asks ONE clarifying question or returns a reel.

    Returns {"action": "ask", "question"} or {"action": "reel", "clips", "note", "label"},
    or None when no provider is configured / the call fails (caller falls back to keywords).
    """
    settings = get_settings()
    if not settings.anthropic_api_key and not settings.openai_api_key:
        return None

    catalog = "\n".join(
        f"{clip['id']}: [{clip['duration']}s] {clip['headline']} — {clip['description'][:140]}"
        for clip in clips
    )
    system = (
        "You are ReplaysAI's reel director. You build highlight reels for a fan from a fixed "
        "catalog of real clips from one game.\n"
        "Decide between two actions each turn:\n"
        "1. If the fan's request is ambiguous about WHAT to feature (player, team, type of "
        "moments) or HOW LONG the reel should be, and the conversation has not already "
        "answered it, ask exactly ONE short, friendly clarifying question (offer concrete "
        "options like 2, 5, or 10 minutes).\n"
        "2. Otherwise build the reel: pick matching clips in the order they should play, "
        f"keeping total duration near {budget} seconds (the fan's duration words override this).\n"
        "Never ask more than one question total per conversation — if you already asked, build "
        "the best reel you can with what you know.\n"
        "Respond with ONLY JSON, one of:\n"
        '{"action": "ask", "question": "..."}\n'
        '{"action": "generate", "clip_ids": ["id", ...], "label": "short reel title", '
        '"note": "one sentence telling the fan what the reel covers"}\n'
        f"\nClip catalog:\n{catalog}"
    )

    try:
        if settings.anthropic_api_key:
            import anthropic

            response = anthropic.Anthropic(api_key=settings.anthropic_api_key).messages.create(
                model=settings.anthropic_model,
                max_tokens=500,
                system=system,
                messages=_agent_turns(body),
            )
            raw = response.content[0].text
        else:
            from openai import OpenAI

            response = OpenAI(api_key=settings.openai_api_key).chat.completions.create(
                model=settings.openai_model,
                max_tokens=500,
                messages=[{"role": "system", "content": system}, *_agent_turns(body)],
            )
            raw = response.choices[0].message.content or ""

        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None
        parsed = json.loads(match.group(0))

        if parsed.get("action") == "ask" and parsed.get("question"):
            return {"action": "ask", "question": str(parsed["question"])}

        by_id = {clip["id"]: clip for clip in clips}
        ordered = [by_id[str(clip_id)] for clip_id in parsed.get("clip_ids", []) if str(clip_id) in by_id]
        if not ordered:
            return None
        selected, _ = _fill_budget(ordered, budget)
        return {
            "action": "reel",
            "clips": selected,
            "label": str(parsed.get("label") or f"Custom reel — {body.prompt[:60]}"),
            "note": str(parsed.get("note") or "Here is the reel you asked for."),
        }
    except Exception as exc:
        print(f"[reels] LLM agent failed ({settings.anthropic_model}): {exc}")
        return None


def _is_vague(body: ReelRequest, budget_hint: int | None) -> bool:
    tokens = [
        token for token in re.findall(r"[a-z0-9']+", body.prompt.lower())
        if len(token) > 2 and token not in _STOPWORDS
    ]
    return not tokens and budget_hint is None


def _already_asked(body: ReelRequest) -> bool:
    return any(turn.role == "assistant" for turn in body.messages)


@router.post("/{game_id}/reels/generate")
def generate_reel(game_id: int, body: ReelRequest):
    _, _, summary = _resolve_game(game_id)
    clips = extract_summary_videos(summary)
    if not clips:
        raise HTTPException(
            status_code=404,
            detail="ESPN has not published video clips for this game yet, so a custom reel cannot be built.",
        )

    budget_hint = body.max_seconds or _budget_from_prompt(body.prompt)
    budget = budget_hint or 300

    result = _reel_agent_llm(body, clips, budget)
    source = "llm"
    if result is None:
        # Keyword fallback keeps the same ask-then-generate shape.
        if _is_vague(body, budget_hint) and not _already_asked(body):
            result = {
                "action": "ask",
                "question": (
                    "What should this reel focus on — a specific player, one team's plays, or the "
                    "game-defining moments? And how long do you want it: 2, 5, or 10 minutes?"
                ),
            }
        else:
            selected, note = _select_clips_keywords(body.prompt, clips, budget)
            result = {
                "action": "reel",
                "clips": selected,
                "label": f"Custom reel — {body.prompt[:60]}",
                "note": note,
            }
        source = "keyword"

    if result["action"] == "ask":
        return {"game_id": game_id, "action": "ask", "question": result["question"], "source": source}

    return {
        "game_id": game_id,
        "action": "reel",
        "prompt": body.prompt,
        "label": result["label"],
        "clips": result["clips"],
        "estimated_seconds": sum(clip.get("duration") or 30 for clip in result["clips"]),
        "note": result["note"],
        "source": source,
    }
