"""
Two-host broadcast script generator.

Generates a NotebookLM-style podcast conversation between two hosts:
- "play": energetic play-by-play voice
- "analyst": tactical, deeper commentary

The script is structured as timed turns mapped to StoryReelPlayer scene types
so the visual player and audio stay synchronized.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException

from api.espn_public import (
    extract_summary_leaders,
    extract_summary_plays,
    fetch_espn_game_by_id,
    fetch_espn_summary_by_id,
)
from api.recaps import _lead_changes, _period_scores, llm_text
from config import get_settings

router = APIRouter(prefix="/api/games", tags=["broadcast"])

TIER_SECONDS = {120: "2min", 300: "5min", 600: "10min"}
TIER_TURNS = {120: 12, 300: 30, 600: 60}


def _build_broadcast_llm(facts: dict, seconds: int) -> list[dict] | None:
    settings = get_settings()
    if not settings.anthropic_api_key:
        return None

    a, h = facts["away"], facts["home"]
    leaders = facts.get("leaders") or []
    periods = facts.get("periods") or []
    lc = facts.get("lead_changes", 0)
    aa, ha = a.get("abbreviation", "?"), h.get("abbreviation", "?")
    as_, hs = facts.get("away_score"), facts.get("home_score")
    key_plays = facts.get("key_plays") or []

    leader_lines = "\n".join(
        f"{r['team']} — {r['player']}: {r['stat_line']} ({r['category']})"
        for r in leaders[:8]
    )
    period_line = " | ".join(
        f"{p['label']}: {aa} {p['away']} – {ha} {p['home']}" for p in periods
    )
    play_lines = "\n".join(
        f"  Q{p.get('period')} {p.get('clock','')}: {p.get('description','')}"
        for p in key_plays[:20]
    )

    n_turns = TIER_TURNS.get(seconds, 30)
    max_tokens = 900 if seconds <= 120 else 2200 if seconds <= 300 else 4000

    winner = h.get("name") if (hs or 0) >= (as_ or 0) else a.get("name")
    margin = abs((hs or 0) - (as_ or 0))
    game_narrative = (
        "close game" if margin <= 5 else
        "comfortable win" if margin >= 15 else
        "competitive game"
    )

    system = (
        "You are writing a two-host sports podcast broadcast script. "
        "These two hosts have been deeply briefed on this specific game — every turn must reference "
        "actual plays, actual player names, actual stats, and actual periods from the data provided.\n\n"
        "HOST_PLAY (host='play'): The energetic play-by-play voice. Narrates what happened in real time — "
        "calls out specific plays, scoring sequences, clutch moments by player name. Excited, fast-paced.\n\n"
        "HOST_ANALYST (host='analyst'): The tactical expert. Explains *why* things happened — "
        "matchup exploits, defensive breakdowns, coaching decisions, efficiency numbers. Calm, incisive, specific.\n\n"
        "Rules:\n"
        "- Ground EVERY line in the actual data — never invent stats, plays, injuries, or quotes.\n"
        "- Reference players by full name on first mention, last name after.\n"
        "- The analyst must always go deeper than the play-by-play — explain causality, not just events.\n"
        "- Alternate hosts naturally; avoid two consecutive same-host turns unless dramatically necessary.\n"
        f"- Write exactly {n_turns} turns total.\n\n"
        "SCENE TYPES:\n"
        "  title   — game overview / setup\n"
        "  moment  — specific key play or clutch sequence\n"
        "  stat    — statistical deep-dive or efficiency insight\n"
        "  run     — scoring run, momentum shift, or quarter recap\n"
        "  verdict — game conclusion, impact, what it means\n\n"
        "Respond ONLY with a valid JSON array (no markdown fences):\n"
        '[{"host":"play","text":"...","scene_type":"title","duration_hint":8}, ...]\n\n'
        "duration_hint: estimated seconds to speak this line (5-18)"
    )
    prompt = (
        f"Game: {a.get('name')} {as_} at {h.get('name')} {hs} ({facts.get('date','')})\n"
        f"Sport: {facts.get('sport','')}\n"
        f"Result: {winner} wins — {game_narrative}, margin of {margin}\n"
        f"Lead changes: {lc}\n\n"
        f"Quarter-by-quarter scoring:\n{period_line or 'n/a'}\n\n"
        f"Statistical leaders:\n{leader_lines or 'n/a'}\n\n"
        f"Key plays:\n{play_lines or 'not available'}\n\n"
        f"Task: Write a {seconds // 60}-minute broadcast conversation ({n_turns} turns) "
        f"that a die-hard fan would learn something new from. "
        f"The analyst must explain WHY {winner} won with specific tactical observations from the data above."
    )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        raw = ""
        for model in settings.anthropic_models:
            try:
                resp = client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = resp.content[0].text.strip()
                break
            except Exception as exc:
                print(f"[broadcast] {model}: {exc}")
        if not raw:
            return None
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if not m:
            return None
        turns = json.loads(m.group(0))
        if not isinstance(turns, list):
            return None
        cleaned = []
        for t in turns:
            if not isinstance(t, dict):
                continue
            host = str(t.get("host", "play"))
            if host not in ("play", "analyst"):
                host = "play"
            scene = str(t.get("scene_type", "moment"))
            if scene not in ("title", "moment", "stat", "run", "verdict"):
                scene = "moment"
            cleaned.append({
                "host": host,
                "text": str(t.get("text", ""))[:400],
                "scene_type": scene,
                "duration_hint": max(4, min(20, int(t.get("duration_hint", 8)))),
            })
        return cleaned if cleaned else None
    except Exception as exc:
        print(f"[broadcast] LLM failed: {exc}")
        return None


def _build_broadcast_fallback(facts: dict, seconds: int) -> list[dict]:
    a, h = facts["away"], facts["home"]
    aa, ha = a.get("abbreviation", "?"), h.get("abbreviation", "?")
    as_, hs = facts.get("away_score"), facts.get("home_score")
    leaders = facts.get("leaders") or []
    periods = facts.get("periods") or []
    lc = facts.get("lead_changes", 0)
    winner, loser = (h, a) if (hs or 0) >= (as_ or 0) else (a, h)
    wsc = hs if (hs or 0) >= (as_ or 0) else as_
    lsc = as_ if (hs or 0) >= (as_ or 0) else hs

    turns: list[dict] = [
        {"host": "play", "text": f"Welcome to the breakdown of {a.get('name')} versus {h.get('name')}. Final score: {aa} {as_}, {ha} {hs}.", "scene_type": "title", "duration_hint": 8},
        {"host": "analyst", "text": f"{winner.get('name')} wins this one {wsc} to {lsc}. There were {lc} lead change{'s' if lc != 1 else ''} — so this was {'a real back-and-forth' if lc >= 4 else 'a fairly decisive result'}.", "scene_type": "title", "duration_hint": 10},
    ]
    for i, p in enumerate(periods[:4]):
        host = "play" if i % 2 == 0 else "analyst"
        turns.append({"host": host, "text": f"In the {p['label']}: {aa} scored {p['away']}, {ha} scored {p['home']}.", "scene_type": "run", "duration_hint": 7})

    for i, ldr in enumerate(leaders[:4]):
        host = "analyst" if i % 2 == 0 else "play"
        turns.append({"host": host, "text": f"{ldr['player']} for {ldr['team']}: {ldr['stat_line']}. That {ldr['category'].lower()} line tells the story.", "scene_type": "stat", "duration_hint": 8})

    turns.append({"host": "play", "text": f"{winner.get('name')} takes it. What stands out to you as the decisive factor?", "scene_type": "verdict", "duration_hint": 7})
    turns.append({"host": "analyst", "text": f"The {winner.get('name')} controlled the critical stretches and protected the lead when it mattered. That's how you win.", "scene_type": "verdict", "duration_hint": 10})

    if seconds >= 300:
        turns.insert(4, {"host": "analyst", "text": f"Let me zoom in on the scoring trend. {aa} averaged {(as_ or 0) / max(1, len(periods)):.0f} points per period. {ha} answered at {(hs or 0) / max(1, len(periods)):.0f}. The efficiency gap was the story.", "scene_type": "stat", "duration_hint": 11})

    return turns


@router.post("/{game_id}/broadcast")
async def generate_broadcast(game_id: int, seconds: int = 300):
    resolved_game = fetch_espn_game_by_id(game_id)
    resolved_summary = fetch_espn_summary_by_id(game_id)
    if not resolved_game or not resolved_summary:
        raise HTTPException(status_code=404, detail="Game not found")
    sport, game = resolved_game
    _, summary = resolved_summary

    plays = extract_summary_plays(summary, sport, limit=400)
    all_plays = [p for p in plays if p.get("play_type") != "other"]
    key_plays = [
        p for p in all_plays
        if any(kw in (p.get("description") or "").lower()
               for kw in ("three", "dunk", "layup", "touchdown", "interception", "sack",
                          "field goal", "three-pointer", "free throw", "buzzer", "overtime"))
    ][-25:]

    facts = {
        "sport": sport,
        "away": game["away_team"],
        "home": game["home_team"],
        "away_score": game.get("away_score"),
        "home_score": game.get("home_score"),
        "date": (game.get("game_date") or "")[:10],
        "periods": _period_scores(plays, sport),
        "lead_changes": _lead_changes(plays),
        "leaders": extract_summary_leaders(summary),
        "key_plays": key_plays,
    }

    with ThreadPoolExecutor(max_workers=1) as ex:
        llm_fut = ex.submit(_build_broadcast_llm, facts, seconds)
        turns = llm_fut.result()

    source = "llm"
    if turns is None:
        turns = _build_broadcast_fallback(facts, seconds)
        source = "fallback"

    total_duration = sum(t["duration_hint"] for t in turns)
    return {
        "game_id": game_id,
        "seconds": seconds,
        "source": source,
        "turns": turns,
        "total_duration": total_duration,
        "away": game["away_team"],
        "home": game["home_team"],
    }
