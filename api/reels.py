"""Agent-generated story reels.

A reel here is not trimmed broadcast footage — it is a screenplay the agent
builds from structured game data (play-by-play, period scores, scoring runs,
lead changes, statistical leaders): a timed sequence of scenes with narration
explaining why each moment mattered. The frontend renders it as an animated
story. Depth scales with requested length: ~30s is the emotional punchline,
2 minutes is a structured narrative, 5-10 minutes approaches a mini-documentary.
"""
import json
import re
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.espn_public import (
    extract_summary_leaders,
    extract_summary_plays,
    fetch_espn_game_by_id,
    fetch_espn_summary_by_id,
)
from api.recaps import _lead_changes, _period_label, _period_scores
from config import get_settings

router = APIRouter(prefix="/api/games", tags=["reels"])

CUT_LENGTHS = [120, 300, 600]

_PLAY_WEIGHTS = {
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

_PLAY_PHRASES = {
    "dunk": "A statement at the rim",
    "three_pointer": "From way downtown",
    "block": "Rejected at the summit",
    "steal": "Picked clean",
    "shot": "A bucket when it counted",
    "free_throw": "Points from the stripe",
    "touchdown": "Six points on the board",
    "interception": "Turned over at the worst time",
    "sack": "The pocket collapses",
    "field_goal": "Three points off the boot",
    "turnover": "A costly giveaway",
    "assist": "Vision finds the open man",
}


def _resolve_game(game_id: int) -> tuple[str, dict, dict]:
    resolved_game = fetch_espn_game_by_id(game_id)
    resolved_summary = fetch_espn_summary_by_id(game_id)
    if not resolved_game or not resolved_summary:
        raise HTTPException(status_code=404, detail="Game not found")
    sport, game_data = resolved_game
    _, summary = resolved_summary
    return sport, game_data, summary


def _biggest_run(plays: list[dict], away_abbr: str, home_abbr: str) -> dict | None:
    """Longest stretch of unanswered points."""
    best = None
    run_side, run_points = None, 0
    last_away = last_home = 0
    for play in plays:
        away, home = play.get("away_score"), play.get("home_score")
        if away is None or home is None:
            continue
        delta_away, delta_home = away - last_away, home - last_home
        last_away, last_home = away, home
        if delta_away < 0 or delta_home < 0:
            run_side, run_points = None, 0
            continue
        if delta_away > 0 and delta_home > 0:
            run_side, run_points = None, 0
            continue
        side = "away" if delta_away > 0 else "home" if delta_home > 0 else None
        if side is None:
            continue
        if side == run_side:
            run_points += delta_away + delta_home
        else:
            run_side, run_points = side, delta_away + delta_home
        if best is None or run_points > best["points"]:
            best = {
                "team": away_abbr if run_side == "away" else home_abbr,
                "points": run_points,
                "period": play.get("period"),
                "score": {"away": away, "home": home},
            }
    return best if best and best["points"] >= 8 else None


def _story_facts(sport: str, game: dict, summary: dict) -> dict:
    plays = extract_summary_plays(summary, sport, limit=500)
    for index, play in enumerate(plays):
        play["ref"] = index
        weight = _PLAY_WEIGHTS.get(play.get("play_type") or "other", 1)
        if "miss" in (play.get("description") or "").lower():
            weight = max(1, weight - 6)
        play["weight"] = weight
    away, home = game["away_team"], game["home_team"]
    away_abbr = away.get("abbreviation") or "AWY"
    home_abbr = home.get("abbreviation") or "HME"
    return {
        "sport": sport,
        "away": away.get("name") or "Away",
        "home": home.get("name") or "Home",
        "away_abbr": away_abbr,
        "home_abbr": home_abbr,
        "away_score": game.get("away_score"),
        "home_score": game.get("home_score"),
        "date": (game.get("game_date") or "")[:10],
        "status": game.get("status"),
        "plays": plays,
        "periods": _period_scores(plays, sport),
        "lead_changes": _lead_changes(plays),
        "run": _biggest_run(plays, away_abbr, home_abbr),
        "leaders": extract_summary_leaders(summary),
    }


def _score_state(facts: dict, play: dict) -> str:
    away, home = play.get("away_score"), play.get("home_score")
    if away is None or home is None:
        return ""
    if away == home:
        return f"{facts['away_abbr']} and {facts['home_abbr']} level at {away}"
    leader = facts["away_abbr"] if away > home else facts["home_abbr"]
    return f"{leader} up {max(away, home)}-{min(away, home)}"


def _moment_scene(facts: dict, play: dict, duration: int, narration: str | None = None) -> dict:
    period = play.get("period") or 1
    label = _period_label(facts["sport"], period)
    if narration is None:
        phrase = _PLAY_PHRASES.get(play.get("play_type") or "", "The moment lands")
        state = _score_state(facts, play)
        clock = play.get("clock") or ""
        narration = f"{phrase} — {state}" + (f" with {clock} left in {label}." if clock else f" in {label}.")
    return {
        "type": "moment",
        "duration": duration,
        "heading": f"{label} · {play.get('clock') or ''}".strip(" ·"),
        "text": play.get("description") or "",
        "narration": narration,
        "period": period,
        "clock": play.get("clock"),
        "score": {"away": play.get("away_score"), "home": play.get("home_score")},
        "play_type": play.get("play_type") or "other",
    }


def _stat_scene(facts: dict, duration: int, narration: str | None = None) -> dict:
    return {
        "type": "stat",
        "duration": duration,
        "heading": "By the numbers",
        "text": "Who carried it",
        "narration": narration or "The box score tells you who decided this one.",
        "stats": [
            {"label": f"{row['player']} ({row['team']})", "value": f"{row['stat_line']} {row['category'].lower()}"}
            for row in facts["leaders"][:6]
        ],
    }


def _title_scene(facts: dict, focus: str, duration: int = 7) -> dict:
    return {
        "type": "title",
        "duration": duration,
        "heading": facts["date"],
        "text": f"{facts['away']} @ {facts['home']}",
        "narration": focus,
        "score": {"away": None, "home": None},
    }


def _verdict_scene(facts: dict, duration: int = 9, narration: str | None = None) -> dict:
    if facts["away_score"] is not None and facts["home_score"] is not None:
        winner = facts["home"] if facts["home_score"] > facts["away_score"] else facts["away"]
        margin = abs(facts["home_score"] - facts["away_score"])
        text = f"Final: {facts['away_abbr']} {facts['away_score']} — {facts['home_abbr']} {facts['home_score']}"
        default = (
            f"{winner} by {margin}, in a game that flipped {facts['lead_changes']} "
            f"time{'s' if facts['lead_changes'] != 1 else ''}. That's the story."
        )
    else:
        text = f"{facts['away_abbr']} vs {facts['home_abbr']} — still being written"
        default = "This one isn't over yet."
    return {
        "type": "verdict",
        "duration": duration,
        "heading": "Full time",
        "text": text,
        "narration": narration or default,
        "score": {"away": facts["away_score"], "home": facts["home_score"]},
    }


def _build_story_data(facts: dict, duration: int, focus: str | None = None) -> dict:
    """Deterministic screenplay straight from the data — used when no LLM is
    configured (or the call fails) and for the instant pre-built cuts."""
    n_scenes = max(4, min(48, round(duration / 9)))
    scene_seconds = max(6, min(14, round(duration / n_scenes)))

    scenes = [_title_scene(facts, focus or f"The story of {facts['away_abbr']} at {facts['home_abbr']}")]
    reserved = 2  # title + verdict

    if facts["leaders"]:
        reserved += 1
    include_breaks = duration >= 240 and facts["periods"]
    if include_breaks:
        reserved += min(3, len(facts["periods"]))
    include_run = duration >= 120 and facts["run"] is not None
    if include_run:
        reserved += 1

    moment_budget = max(2, n_scenes - reserved)
    candidates = sorted(facts["plays"], key=lambda p: (-p["weight"], p["ref"]))[:moment_budget]
    moments = sorted(candidates, key=lambda p: p["ref"])

    breaks_at = {}
    if include_breaks:
        for snapshot in facts["periods"][:-1][:3]:
            breaks_at[snapshot["label"]] = {
                "type": "break",
                "duration": scene_seconds,
                "heading": f"End of {snapshot['label']}",
                "text": f"{facts['away_abbr']} {snapshot['away']} — {facts['home_abbr']} {snapshot['home']}",
                "narration": "The chapter closes; the chess match resets.",
                "score": {"away": snapshot["away"], "home": snapshot["home"]},
            }

    seen_periods: set[int] = set()
    for play in moments:
        period = play.get("period") or 1
        prev_label = _period_label(facts["sport"], period - 1) if period > 1 else None
        if prev_label and prev_label in breaks_at and period not in seen_periods:
            scenes.append(breaks_at.pop(prev_label))
        seen_periods.add(period)
        scenes.append(_moment_scene(facts, play, scene_seconds))

    if include_run:
        run = facts["run"]
        scenes.append({
            "type": "run",
            "duration": scene_seconds,
            "heading": f"{run['points']}-0 run",
            "text": f"{run['team']} take over in {_period_label(facts['sport'], run['period'] or 1)}",
            "narration": f"{run['points']} unanswered points — the stretch that bent the game.",
            "score": run["score"],
        })
    if facts["leaders"]:
        scenes.append(_stat_scene(facts, scene_seconds))
    scenes.append(_verdict_scene(facts))

    return {
        "title": f"{facts['away_abbr']} @ {facts['home_abbr']} — {focus or 'the full story'}",
        "focus": focus or "full_summary",
        "duration_seconds": sum(scene["duration"] for scene in scenes),
        "scene_count": len(scenes),
        "scenes": scenes,
        "generated_by": "data",
    }


def _scene_guidance(duration: int) -> str:
    if duration <= 45:
        return "4-6 scenes: title, the 2-3 punchline moments, verdict. Pure emotional arc."
    if duration <= 150:
        return ("10-14 scenes: title, key moments in story order, one run or break scene, "
                "one stat scene, verdict. A structured narrative of the game.")
    if duration <= 360:
        return ("20-30 scenes: mini-documentary depth — chapter breaks per period, runs, "
                "tactical context in narration, player spotlight via stat scenes, verdict.")
    return ("34-46 scenes: full documentary treatment — possession-level beats, both teams' "
            "perspectives, multiple stat scenes, every momentum swing narrated.")


def _build_story_llm(body: "ReelRequest", facts: dict, duration: int) -> dict | None:
    """Conversational director. Returns {"action": "ask", ...},
    {"action": "story", ...} or None to fall back to the data builder."""
    settings = get_settings()
    if not settings.anthropic_api_key and not settings.openai_api_key:
        return None

    catalog_plays = sorted(facts["plays"], key=lambda p: (-p["weight"], p["ref"]))[:90]
    catalog = "\n".join(
        f"{p['ref']}: {_period_label(facts['sport'], p.get('period') or 1)} {p.get('clock') or ''} "
        f"[{facts['away_abbr']} {p.get('away_score')}-{p.get('home_score')} {facts['home_abbr']}] "
        f"({p.get('play_type')}) {p.get('description')}"
        for p in sorted(catalog_plays, key=lambda p: p["ref"])
    )
    leaders = "\n".join(
        f"{row['team']} — {row['player']}: {row['stat_line']} ({row['category']})" for row in facts["leaders"]
    )
    periods = "; ".join(
        f"{p['label']} {facts['away_abbr']} {p['away']}-{p['home']} {facts['home_abbr']}" for p in facts["periods"]
    )
    run = facts["run"]
    run_line = f"{run['team']} had {run['points']} unanswered in period {run['period']}" if run else "none detected"

    system = (
        "You are ReplaysAI's reel director. You turn one game's structured data into a "
        "short-form story reel: a timed sequence of scenes with narration, rendered as an "
        "animated story (not video clips). You decide the storyline — comeback, star "
        "takeover, defensive collapse, two-team duel, or full summary — from the data and "
        "the fan's request.\n\n"
        "Each turn, do ONE of:\n"
        "1. If the request is ambiguous about focus or length and the conversation hasn't "
        "already settled it, ask exactly ONE short clarifying question (offer 30 seconds, "
        "2, 5, or 10 minutes). Never ask twice in one conversation.\n"
        f"2. Otherwise output the screenplay. Target total duration: {duration} seconds. "
        f"{_scene_guidance(duration)}\n\n"
        "Scene rules:\n"
        "- 'moment' scenes MUST carry a play_ref from the catalog; never invent plays, "
        "scores, or stats. Narration explains WHY the moment mattered to the storyline.\n"
        "- 'title' opens (text = matchup hook), 'verdict' closes (narration = the takeaway).\n"
        "- 'break' marks a period/chapter transition; 'run' marks a momentum swing; 'stat' "
        "shows numbers (use the leaders data; stats = [{label, value}]).\n"
        "- duration is per-scene seconds (5-14). Narration: 1-2 punchy sentences, "
        "documentary voice-over style.\n\n"
        "Respond with ONLY JSON, one of:\n"
        '{"action": "ask", "question": "..."}\n'
        '{"action": "generate", "title": "...", "focus": "...", "scenes": [\n'
        '  {"type": "title", "duration": 6, "text": "...", "heading": "...", "narration": "..."},\n'
        '  {"type": "moment", "duration": 9, "play_ref": 12, "narration": "..."},\n'
        '  {"type": "break"|"run", "duration": 7, "heading": "...", "text": "...", "narration": "..."},\n'
        '  {"type": "stat", "duration": 8, "heading": "...", "narration": "...", "stats": [{"label": "...", "value": "..."}]},\n'
        '  {"type": "verdict", "duration": 9, "text": "...", "narration": "..."}\n'
        "]}\n\n"
        f"GAME DATA\nMatchup: {facts['away']} ({facts['away_abbr']}) at {facts['home']} "
        f"({facts['home_abbr']}), {facts['date']}\n"
        f"Final: {facts['away_abbr']} {facts['away_score']} - {facts['home_abbr']} {facts['home_score']}\n"
        f"Period scores: {periods}\nLead changes: {facts['lead_changes']}\nBiggest run: {run_line}\n"
        f"Leaders:\n{leaders}\n\nPlay catalog:\n{catalog}"
    )

    turns = [
        {"role": turn.role, "content": turn.text}
        for turn in body.messages[-10:]
        if turn.text.strip()
    ]
    if not turns or turns[-1]["role"] != "user" or turns[-1]["content"] != body.prompt:
        turns.append({"role": "user", "content": body.prompt})

    max_tokens = min(8000, 900 + round(duration / 9) * 90)
    try:
        if settings.anthropic_api_key:
            import anthropic

            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            raw = ""
            for model in settings.anthropic_models:
                try:
                    response = client.messages.create(
                        model=model,
                        max_tokens=max_tokens,
                        system=system,
                        messages=turns,
                    )
                    raw = response.content[0].text
                    break
                except Exception as exc:
                    print(f"[reels] story agent failed ({model}): {exc}")
            if not raw:
                return None
        else:
            from openai import OpenAI

            response = OpenAI(api_key=settings.openai_api_key).chat.completions.create(
                model=settings.openai_model,
                max_tokens=max_tokens,
                messages=[{"role": "system", "content": system}, *turns],
            )
            raw = response.choices[0].message.content or ""

        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None
        parsed = json.loads(match.group(0))

        if parsed.get("action") == "ask" and parsed.get("question"):
            return {"action": "ask", "question": str(parsed["question"])}

        by_ref = {p["ref"]: p for p in facts["plays"]}
        scenes = []
        for raw_scene in parsed.get("scenes", [])[:50]:
            scene_type = raw_scene.get("type")
            seconds = raw_scene.get("duration")
            seconds = max(5, min(14, int(seconds))) if isinstance(seconds, (int, float)) else 8
            narration = str(raw_scene.get("narration") or "")
            if scene_type == "moment":
                play = by_ref.get(raw_scene.get("play_ref"))
                if not play:
                    continue
                scenes.append(_moment_scene(facts, play, seconds, narration or None))
            elif scene_type == "stat":
                stats = [
                    {"label": str(s.get("label") or ""), "value": str(s.get("value") or "")}
                    for s in raw_scene.get("stats") or []
                    if s.get("label")
                ]
                scene = _stat_scene(facts, seconds, narration or None)
                if stats:
                    scene["stats"] = stats[:8]
                if raw_scene.get("heading"):
                    scene["heading"] = str(raw_scene["heading"])
                scenes.append(scene)
            elif scene_type in ("title", "verdict", "break", "run"):
                base = _title_scene(facts, narration or "", seconds) if scene_type == "title" else (
                    _verdict_scene(facts, seconds, narration or None) if scene_type == "verdict" else {
                        "type": scene_type,
                        "duration": seconds,
                        "heading": str(raw_scene.get("heading") or ""),
                        "text": str(raw_scene.get("text") or ""),
                        "narration": narration,
                        "score": {"away": None, "home": None},
                    }
                )
                if raw_scene.get("text") and scene_type in ("title", "verdict"):
                    base["text"] = str(raw_scene["text"])
                if raw_scene.get("heading"):
                    base["heading"] = str(raw_scene["heading"])
                scenes.append(base)

        if len(scenes) < 3:
            return None
        return {
            "action": "story",
            "title": str(parsed.get("title") or f"{facts['away_abbr']} @ {facts['home_abbr']}"),
            "focus": str(parsed.get("focus") or "full_summary"),
            "duration_seconds": sum(scene["duration"] for scene in scenes),
            "scene_count": len(scenes),
            "scenes": scenes,
            "generated_by": "llm",
        }
    except Exception as exc:
        print(f"[reels] story agent failed: {exc}")
        return None


@router.get("/{game_id}/reels")
def get_reel_cuts(game_id: int):
    sport, game_data, summary = _resolve_game(game_id)
    facts = _story_facts(sport, game_data, summary)
    return {
        "game_id": game_id,
        "play_count": len(facts["plays"]),
        "cuts": [
            {
                "label": f"{length // 60} min story",
                "duration_seconds": length,
                "story": _build_story_data(facts, length),
            }
            for length in CUT_LENGTHS
        ],
        "rendering": {
            "playback": "story_engine",
            "reason": (
                "Cuts are agent-built story reels rendered from real play-by-play, scoring "
                "runs, and box-score data. Ask the reel agent for a custom focus or length — "
                "the longer the reel, the deeper the story."
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
    "story", "stories", "recap", "about", "around",
}


def _budget_from_prompt(prompt: str) -> int | None:
    text = prompt.lower()
    minutes = re.search(r"(\d+)\s*-?\s*min", text)
    if minutes:
        return max(30, min(900, int(minutes.group(1)) * 60))
    seconds = re.search(r"(\d+)\s*-?\s*sec", text)
    if seconds:
        return max(20, min(900, int(seconds.group(1))))
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
    sport, game_data, summary = _resolve_game(game_id)
    facts = _story_facts(sport, game_data, summary)
    if not facts["plays"]:
        raise HTTPException(
            status_code=404,
            detail="Play-by-play is not available for this game yet, so a story reel cannot be built.",
        )

    budget_hint = body.max_seconds or _budget_from_prompt(body.prompt)
    budget = budget_hint or 120

    result = _build_story_llm(body, facts, budget)
    source = "llm"
    if result is None:
        # Data fallback keeps the same ask-then-generate shape.
        if _is_vague(body, budget_hint) and not _already_asked(body):
            result = {
                "action": "ask",
                "question": (
                    "What should this reel focus on — a player, one team's run, or the full "
                    "game story? And how deep should it go: 30 seconds, 2, 5, or 10 minutes?"
                ),
            }
        else:
            result = {"action": "story", **_build_story_data(facts, budget, focus=body.prompt[:80])}
        source = "fallback"

    if result["action"] == "ask":
        return {"game_id": game_id, "action": "ask", "question": result["question"], "source": source}

    story = {key: value for key, value in result.items() if key != "action"}
    return {
        "game_id": game_id,
        "action": "story",
        "prompt": body.prompt,
        "story": story,
        "note": f"Built a {max(1, round(story['duration_seconds'] / 60))}-minute story: {story['title']}",
        "source": source,
    }
