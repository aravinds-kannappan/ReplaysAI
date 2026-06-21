"""Real-video story reels.

A reel here is real ESPN highlight footage (HLS/MP4 clips) curated by the agent,
not trimmed-from-the-start broadcast and not a text screenplay. The tiers
summarize the ENTIRE game at increasing depth:

- 2 min  -> a quick rundown: a handful of clips spread across the whole game
- 5 min  -> a fuller recap: more clips, still spanning the whole game
- 10 min -> the meticulous cut: most/all clips

A conversational director also builds a focused reel on request — "only Q4",
"every foul", "Wembanyama's takeover" — by selecting the matching clips and
writing one-line narration per clip.
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.espn_public import (
    extract_summary_leaders,
    extract_summary_plays,
    extract_summary_videos,
    fetch_espn_game_by_id,
    fetch_espn_game_summary,
    fetch_espn_games,
    fetch_espn_summary_by_id,
)
from api.recaps import _lead_changes, _period_scores, llm_text
from config import get_settings

router = APIRouter(prefix="/api/games", tags=["reels"])

CUT_TIERS = [
    ("2 min story", 120, "A quick rundown of the entire game."),
    ("5 min story", 300, "A fuller recap across every quarter."),
    ("10 min story", 600, "The meticulous, detailed cut."),
]


def _resolve(game_id: int):
    resolved_game = fetch_espn_game_by_id(game_id)
    resolved_summary = fetch_espn_summary_by_id(game_id)
    if not resolved_game or not resolved_summary:
        raise HTTPException(status_code=404, detail="Game not found")
    sport, game_data = resolved_game
    _, summary = resolved_summary
    return sport, game_data, summary


_HIGHLIGHT_KW = [
    "dunk", "three", "3-point", "layup", "jumper", "basket", "bucket", "block", "steal",
    "and-one", "alley", "poster", "buzzer", "clutch", "run", "go-ahead", "game-winner",
    "overtime", "quarter", "half", "touchdown", " td", "field goal", "sack", "interception",
    "fumble", "pass", "rush", "score", "highlight", "top play", "best play",
]
_POSTGAME_KW = [
    "parade", "press conference", "interview", "reacts", "react", "celebrate", "celebration",
    "trophy", "locker", "postgame", "post-game", "wholesome", "fans", "speech", "confetti",
    "arrives", "red carpet", "champions", "championship parade", "ring", "offseason", "draft",
]


def _clip_score(c: dict) -> int:
    text = f"{c.get('headline','')} {c.get('description','')}".lower()
    s = 0
    for k in _HIGHLIGHT_KW:
        if k in text:
            s += 2
    for k in _POSTGAME_KW:
        if k in text:
            s -= 4
    return s


def _clips_for(summary: dict, sport: str) -> list[dict]:
    clips = extract_summary_videos(summary)
    for clip in clips:
        if not clip.get("duration"):
            clip["duration"] = 24
        clip["_score"] = _clip_score(clip)
    # Prefer in-game highlights; drop clearly post-game/parade clips when there are
    # enough real highlights to fill a reel. Preserve original (broadcast) order.
    highlights = [c for c in clips if c["_score"] > -2]
    return highlights if len(highlights) >= 3 else clips


def _spread(clips: list[dict], target_seconds: int) -> list[dict]:
    """Evenly sample clips across the whole game so a short tier still spans the
    full game rather than just the opening minutes."""
    if not clips:
        return []
    avg = sum(c["duration"] for c in clips) / len(clips)
    want = max(1, min(len(clips), round(target_seconds / max(avg, 8))))
    if want >= len(clips):
        return clips
    step = len(clips) / want
    idxs = sorted({min(len(clips) - 1, int(i * step)) for i in range(want)})
    return [clips[i] for i in idxs]


def _caption(clip: dict) -> str:
    return clip.get("headline") or clip.get("description") or "Highlight"


def _public_clip(clip: dict, narration: str | None = None) -> dict:
    return {
        "id": clip["id"],
        "headline": clip.get("headline") or "",
        "description": clip.get("description") or "",
        "duration": clip.get("duration") or 24,
        "url": clip["url"],
        "thumbnail": clip.get("thumbnail") or "",
        "narration": narration or _caption(clip),
    }


def _winner_side(facts: dict) -> tuple[dict, int]:
    """Returns (winning team dict, win margin). Falls back to home on a tie/None."""
    a, h = facts["away"], facts["home"]
    as_, hs = facts.get("away_score") or 0, facts.get("home_score") or 0
    return (h, hs - as_) if hs >= as_ else (a, as_ - hs)


def _attach_overlays(public_clips: list[dict], facts: dict) -> list[dict]:
    """Attach a typed overlay spec to each clip for the reel player to render as
    React layers: a final scorebug, a rotating leader stat line, and an
    illustrative win-probability read that drifts toward the winner across the
    reel. The win-prob value is a model read, not a measured per-moment number."""
    a, h = facts["away"], facts["home"]
    leaders = facts.get("leaders") or []
    winner, margin = _winner_side(facts)
    total = max(1, len(public_clips))
    # Final win-prob the model lands on, by how lopsided the game was.
    final_wp = max(58, min(92, 60 + margin * 1.4 - facts.get("lead_changes", 0)))
    scorebug = {
        "type": "scorebug",
        "away": {"abbr": a.get("abbreviation"), "score": facts.get("away_score")},
        "home": {"abbr": h.get("abbreviation"), "score": facts.get("home_score")},
    }
    for i, clip in enumerate(public_clips):
        overlays: list[dict] = [scorebug]
        if leaders:
            ldr = leaders[i % len(leaders)]
            overlays.append({
                "type": "statline",
                "player": ldr.get("player"),
                "team": ldr.get("team"),
                "stat_line": ldr.get("stat_line"),
                "category": ldr.get("category"),
            })
        wp = round(50 + (final_wp - 50) * ((i + 1) / total))
        overlays.append({
            "type": "winprob",
            "team": winner.get("abbreviation"),
            "value": wp,
            "model": True,
        })
        clip["overlays"] = overlays
    return public_clips


def _facts(sport: str, game: dict, summary: dict) -> dict:
    plays = extract_summary_plays(summary, sport, limit=400)
    return {
        "sport": sport,
        "away": game["away_team"], "home": game["home_team"],
        "away_score": game.get("away_score"), "home_score": game.get("home_score"),
        "date": (game.get("game_date") or "")[:10],
        "periods": _period_scores(plays, sport),
        "lead_changes": _lead_changes(plays),
        "leaders": extract_summary_leaders(summary),
    }


def _explainer(facts: dict, seconds: int) -> str:
    """A NotebookLM-style spoken-explainer of the game, tiered by depth: 2 min is a
    quick rundown, 5 a fuller recap, 10 a deep dive. LLM when configured, else a
    grounded data-built walkthrough."""
    a, h = facts["away"], facts["home"]
    aa, ha = a.get("abbreviation"), h.get("abbreviation")
    as_, hs = facts["away_score"], facts["home_score"]
    leaders = facts["leaders"]
    periods = facts["periods"]
    lc = facts["lead_changes"]
    leader_lines = "\n".join(f"{r['team']} — {r['player']}: {r['stat_line']} ({r['category']})" for r in leaders[:6])
    period_line = "; ".join(f"{p['label']} {aa} {p['away']}-{p['home']} {ha}" for p in periods)
    depth = "a punchy 2-minute rundown (8-10 sentences with the final score, turning point, and stars)" if seconds <= 120 else (
        "a 5-minute recap (4 sections: opening context, how it unfolded, who decided it, what it means)" if seconds <= 300
        else "a 10-minute deep dive (intro, quarter-by-quarter flow, tactical read, key performers, turning point, fan takeaway, and what to watch next)")

    content = llm_text(
        system=(
            "You are ReplaysAI's game explainer — like a NotebookLM deep dive, but for one game. "
            "Explain the game to a fan conversationally and clearly, grounded ONLY in the supplied "
            "data (final score, period scores, lead changes, statistical leaders). Never invent "
            "plays or numbers. Use Markdown with short headers. The depth must match the request."
        ),
        prompt=(
            f"Game: {a.get('name')} {as_} at {h.get('name')} {hs} ({facts['date']}).\n"
            f"Period scores: {period_line or 'n/a'}\nLead changes: {lc}\nLeaders:\n{leader_lines or 'n/a'}\n\n"
            f"Write {depth} explaining the entire game."
        ),
        max_tokens=650 if seconds <= 120 else 1200 if seconds <= 300 else 2200,
    )
    if content:
        return content

    if as_ is None or hs is None:
        return "Play-by-play for this game is still filling in."
    winner, loser = (h, a) if hs > as_ else (a, h)
    wsc, lsc = (hs, as_) if hs > as_ else (as_, hs)
    period_text = " -> ".join(f"{p['label']}: {aa} {p['away']}-{p['home']} {ha}" for p in periods) or "Period flow is not published yet."
    parts = [
        "## Quick rundown",
        f"{winner.get('name')} beat {loser.get('name')} **{wsc}-{lsc}**, a {abs(hs-as_)}-point game with "
        f"**{lc} lead change{'s' if lc != 1 else ''}** — {'a true back-and-forth fight' if lc >= 4 else 'a steadier result'}.",
        (
            f"The score flow tells the shape of the game: {period_text}. The reel should open with the "
            "headline clip, then move through the moments that show how the margin formed rather than "
            "just stacking isolated highlights."
        ),
    ]
    if leaders:
        top = leaders[: 2 if seconds <= 120 else 4 if seconds <= 300 else 6]
        parts.append("### Who decided it")
        parts += [
            f"- **{r['player']}** ({r['team']}) — {r['stat_line']} {r['category'].lower()}. "
            "This is a primary narration anchor because the box-score line is part of the published summary."
            for r in top
        ]
    if seconds >= 300 and periods:
        parts.append("### How it flowed")
        parts.append(
            f"{period_text}. The 5-minute cut should spend less time on setup and more time on the "
            "middle stretch: where the winner created separation, how the losing side responded, and "
            "which star production kept the game from becoming noise."
        )
    if seconds >= 600:
        parts.append("### The turning point")
        parts.append(
            f"One side seized control during the middle stretch, and {winner.get('name')} managed the "
            f"margin the rest of the way to the {wsc}-{lsc} final. For a 10-minute deep cut, the Reel "
            "Director should preserve every available high-value clip, then let the voice-over explain "
            "why each one mattered to the outcome."
        )
        parts.append("### Fan takeaway")
        parts.append(
            f"For {winner.get('name')} fans, the story is control: finish the job, protect the lead, and "
            f"let the top performers define the final. For {loser.get('name')} fans, the story is diagnosis: "
            "which stretches were survivable, which possessions created the gap, and which player lines still translate forward."
        )
    return "\n\n".join(parts)


def _voice_script(facts: dict, clips: list[dict], seconds: int) -> tuple[str, str]:
    """Narration script for the reel voice agent.

    This is separate from the written recap: it is timed to the actual selected
    clips and intended for a generated reel voice track.
    """
    a, h = facts["away"], facts["home"]
    aa, ha = a.get("abbreviation"), h.get("abbreviation")
    as_, hs = facts["away_score"], facts["home_score"]
    leaders = facts["leaders"]
    periods = facts["periods"]
    period_line = "; ".join(f"{p['label']} {aa} {p['away']}-{p['home']} {ha}" for p in periods)
    leader_lines = "\n".join(f"{r['team']} - {r['player']}: {r['stat_line']} ({r['category']})" for r in leaders[:8])
    clip_lines = "\n".join(
        f"{i + 1}. [{c.get('duration') or 24}s] {c.get('headline') or ''} - {c.get('description') or ''}"
        for i, c in enumerate(clips[:40])
    )
    target_words = 220 if seconds <= 120 else 620 if seconds <= 300 else 1250
    settings = get_settings()

    if settings.anthropic_api_key:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            system = (
                "You are ReplaysAI's reel voice agent. Write the spoken narration for a highlight reel, "
                "not a written recap. Ground every line in the game facts and selected real clips. "
                "Do not invent plays, stats, injuries, quotes, or stakes. Make it energetic, precise, "
                "and personal to the fans watching these teams and stars. Include clip-by-clip cues."
            )
            prompt = (
                f"Game: {a.get('name')} {as_} at {h.get('name')} {hs} ({facts['date']}).\n"
                f"Target reel: {seconds} seconds. Target narration length: about {target_words} words.\n"
                f"Period scores: {period_line or 'n/a'}\n"
                f"Lead changes: {facts['lead_changes']}\n"
                f"Stat leaders:\n{leader_lines or 'n/a'}\n\n"
                f"Selected real clips, in playback order:\n{clip_lines or 'No clips published.'}\n\n"
                "Write a voice-over script with these sections:\n"
                "OPEN, CLIP-BY-CLIP SCRIPT, TRANSITIONS, CLOSE. "
                "Each clip cue should name what the viewer is seeing and why it matters."
            )
            for model in settings.anthropic_models:
                try:
                    resp = client.messages.create(
                        model=model,
                        max_tokens=900 if seconds <= 120 else 1900 if seconds <= 300 else 3600,
                        system=system,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    text = resp.content[0].text.strip()
                    if text:
                        return text, "anthropic"
                except Exception as exc:
                    print(f"[reels] voice agent failed ({model}): {exc}")
        except Exception as exc:
            print(f"[reels] voice agent unavailable: {exc}")

    winner, loser = (h, a) if (hs or 0) > (as_ or 0) else (a, h)
    wsc, lsc = (hs, as_) if (hs or 0) > (as_ or 0) else (as_, hs)
    lines = [
        "OPEN",
        f"{winner.get('name')} took this one over {loser.get('name')}, {wsc}-{lsc}. "
        f"The reel starts with the scoreboard context: {period_line or 'published period scoring is limited'}, "
        f"and a game flow with {facts['lead_changes']} lead change{'s' if facts['lead_changes'] != 1 else ''}.",
        "CLIP-BY-CLIP SCRIPT",
    ]
    for i, clip in enumerate(clips[:12], 1):
        headline = clip.get("headline") or clip.get("description") or "Published highlight"
        lines.append(
            f"{i}. {headline}. Use this moment to show how the game shifted, then connect it back to "
            f"{winner.get('name')}'s control of the final margin."
        )
    if leaders:
        lines.append("CLOSE")
        lines.append(
            "Anchor the closing beat on the published leaders: "
            + "; ".join(f"{r['player']} ({r['team']}) {r['stat_line']}" for r in leaders[:4])
            + ". That is the takeaway fans should remember before the next reel."
        )
    return "\n\n".join(lines), "fallback"


@router.get("/{game_id}/reels")
def get_reel_cuts(game_id: int):
    """Fast: real clips + overlays per tier, no LLM. The reel plays and is voiced
    from per-clip captions immediately; the long-form explainer/voice script is
    generated lazily per tier via /reels/narration so the page never hangs."""
    sport, game_data, summary = _resolve(game_id)
    clips = _clips_for(summary, sport)
    facts = _facts(sport, game_data, summary)
    cuts = []
    for label, seconds, blurb in CUT_TIERS:
        selected = _spread(clips, seconds)
        cuts.append({
            "label": label,
            "target_seconds": seconds,
            "blurb": blurb,
            "clip_count": len(selected),
            "duration_seconds": sum(c["duration"] for c in selected),
            "clips": _attach_overlays([_public_clip(c) for c in selected], facts),
        })
    return {
        "game_id": game_id,
        "clip_count": len(clips),
        "cuts": cuts,
        "rendering": {"playback": "video"},
    }


@router.get("/{game_id}/reels/narration")
def get_reel_narration(game_id: int, seconds: int = 120):
    """On-demand long-form narration for one tier: the spoken voice script + the
    written game explainer. Generated only for the tier the user is viewing."""
    sport, game_data, summary = _resolve(game_id)
    clips = _clips_for(summary, sport)
    facts = _facts(sport, game_data, summary)
    selected = _spread(clips, seconds)
    with ThreadPoolExecutor(max_workers=2) as ex:
        voice_fut = ex.submit(_voice_script, facts, selected, seconds)
        expl_fut = ex.submit(_explainer, facts, seconds)
        voice_script, voice_source = voice_fut.result()
        explainer = expl_fut.result()
    return {
        "game_id": game_id,
        "target_seconds": seconds,
        "explainer": explainer,
        "voice_script": voice_script,
        "voice_source": voice_source,
    }


def build_team_season_reel(team: str, max_games: int = 4) -> dict:
    """A reel compiled from a team's PREVIOUS finished games — real highlight
    clips from each recent game, tiered like the single-game cuts. `team` is a
    'SPORT:ABBR' key (e.g. NBA:BOS)."""
    if ":" not in team:
        raise HTTPException(status_code=400, detail="team must be 'SPORT:ABBR'")
    sport, abbr = team.split(":", 1)
    sport, abbr = sport.upper(), abbr.upper()
    games = fetch_espn_games(sport, limit=80, seasons=2)
    finished = [
        g for g in games
        if g.get("status") == "final"
        and abbr in {
            (g.get("home_team") or {}).get("abbreviation", "").upper(),
            (g.get("away_team") or {}).get("abbreviation", "").upper(),
        }
    ][:max_games]

    all_clips: list[dict] = []
    games_used = []
    for g in finished:
        try:
            summary = fetch_espn_game_summary(sport, g["id"])
            clips = _clips_for(summary, sport)
        except Exception:
            clips = []
        if not clips:
            continue
        matchup = f"{(g.get('away_team') or {}).get('abbreviation')}@{(g.get('home_team') or {}).get('abbreviation')}"
        games_used.append(matchup)
        for c in clips:
            c = dict(c)
            c["headline"] = f"{matchup}: {c.get('headline','')}"
            all_clips.append(c)

    cuts = []
    for label, seconds, blurb in CUT_TIERS:
        selected = _spread(all_clips, seconds)
        cuts.append({
            "label": f"Season {label}",
            "target_seconds": seconds,
            "blurb": blurb,
            "clip_count": len(selected),
            "duration_seconds": sum(c["duration"] for c in selected),
            "clips": [_public_clip(c) for c in selected],
        })
    return {
        "team": team,
        "games_used": games_used,
        "clip_count": len(all_clips),
        "cuts": cuts if all_clips else [],
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
    "build", "create", "generate", "want", "reel", "reels", "video", "clip",
    "clips", "highlight", "highlights", "minute", "minutes", "min", "second",
    "seconds", "sec", "long", "short", "please", "that", "this", "game", "best",
    "top", "every", "just", "only", "story", "recap", "about", "around", "me", "of",
}

_QUARTER_WORDS = {
    "q1": ["q1", "1st quarter", "first quarter"],
    "q2": ["q2", "2nd quarter", "second quarter"],
    "q3": ["q3", "3rd quarter", "third quarter"],
    "q4": ["q4", "4th quarter", "fourth quarter", "final quarter"],
    "ot": ["ot", "overtime"],
    "1st half": ["1st half", "first half"],
    "2nd half": ["2nd half", "second half"],
}


def _budget_from_prompt(prompt: str) -> int | None:
    text = prompt.lower()
    m = re.search(r"(\d+)\s*-?\s*min", text)
    if m:
        return max(30, min(900, int(m.group(1)) * 60))
    s = re.search(r"(\d+)\s*-?\s*sec", text)
    if s:
        return max(20, min(900, int(s.group(1))))
    return None


def _keyword_filter(clips: list[dict], prompt: str) -> list[dict]:
    text = prompt.lower()
    tokens = [t for t in re.findall(r"[a-z0-9']+", text) if len(t) > 2 and t not in _STOPWORDS]
    if not tokens:
        return []
    matched = []
    for clip in clips:
        hay = f"{clip.get('headline','')} {clip.get('description','')}".lower()
        if any(tok in hay for tok in tokens):
            matched.append(clip)
    return matched


def _is_vague(body: ReelRequest, budget_hint: int | None) -> bool:
    tokens = [
        t for t in re.findall(r"[a-z0-9']+", body.prompt.lower())
        if len(t) > 2 and t not in _STOPWORDS
    ]
    return not tokens and budget_hint is None


def _already_asked(body: ReelRequest) -> bool:
    return any(turn.role == "assistant" for turn in body.messages)


def _curate_llm(body: ReelRequest, clips: list[dict], target: int) -> dict | None:
    """LLM director: pick which real clips match the fan's focus, in order, and
    write one-line narration per clip. Returns ask/reel dict, or None to fall back."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        return None

    catalog = "\n".join(
        f"{i} [{c['duration']}s] {c.get('headline','')} — {c.get('description','')[:90]}"
        for i, c in enumerate(clips[:80])
    )
    system = (
        "You are ReplaysAI's reel director. You assemble a highlight reel from a catalog of "
        "REAL video clips of one game. Never invent clips; only reference clip indices from the "
        "catalog. The reel should cover the fan's requested focus (a player, a quarter, a kind "
        "of play like fouls/dunks/threes, or the whole game) and roughly fit the target length.\n\n"
        "Each turn do ONE of:\n"
        "1. If the request is too vague AND you haven't already asked, ask ONE short question "
        "(offer focus options + 2/5/10 minute lengths).\n"
        f"2. Otherwise pick clips. Target total ~{target} seconds. Order them to tell the story. "
        "Write a short 1-line narration per clip (documentary voice-over, grounded in the clip).\n\n"
        "Respond with ONLY JSON, one of:\n"
        '{"action":"ask","question":"..."}\n'
        '{"action":"reel","title":"...","focus":"...","clips":[{"index":3,"narration":"..."}]}\n\n'
        f"CLIP CATALOG:\n{catalog}"
    )
    turns = [{"role": t.role, "content": t.text} for t in body.messages[-10:] if t.text.strip()]
    if not turns or turns[-1]["role"] != "user" or turns[-1]["content"] != body.prompt:
        turns.append({"role": "user", "content": body.prompt})

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        raw = ""
        for model in settings.anthropic_models:
            try:
                resp = client.messages.create(model=model, max_tokens=2000, system=system, messages=turns)
                raw = resp.content[0].text
                break
            except Exception as exc:
                print(f"[reels] director failed ({model}): {exc}")
        if not raw:
            return None

        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None
        parsed = json.loads(match.group(0))
        if parsed.get("action") == "ask" and parsed.get("question"):
            return {"action": "ask", "question": str(parsed["question"])}

        chosen = []
        for item in parsed.get("clips", [])[:60]:
            idx = item.get("index")
            if isinstance(idx, int) and 0 <= idx < len(clips):
                chosen.append(_public_clip(clips[idx], str(item.get("narration") or "") or None))
        if not chosen:
            return None
        return {
            "action": "reel",
            "title": str(parsed.get("title") or "Custom reel"),
            "focus": str(parsed.get("focus") or body.prompt[:60]),
            "clips": chosen,
        }
    except Exception as exc:
        print(f"[reels] director failed: {exc}")
        return None


@router.post("/{game_id}/reels/generate")
def generate_reel(game_id: int, body: ReelRequest):
    sport, game_data, summary = _resolve(game_id)
    clips = _clips_for(summary, sport)
    facts = _facts(sport, game_data, summary)
    if not clips:
        raise HTTPException(
            status_code=404,
            detail="No highlight video is published for this game yet, so a reel can't be built.",
        )

    budget_hint = body.max_seconds or _budget_from_prompt(body.prompt)
    target = budget_hint or 180

    result = _curate_llm(body, clips, target)
    source = "anthropic"
    if result is None:
        source = "fallback"
        if _is_vague(body, budget_hint) and not _already_asked(body):
            result = {
                "action": "ask",
                "question": (
                    "What should this reel focus on — a player, one quarter (e.g. Q4), a kind of "
                    "play (fouls, dunks, threes), or the whole game? And how long: 2, 5, or 10 minutes?"
                ),
            }
        else:
            # Keyword-match the focus against real clip metadata; fall back to a
            # whole-game spread at the requested length.
            text = body.prompt.lower()
            matched = _keyword_filter(clips, body.prompt)
            for label, words in _QUARTER_WORDS.items():
                if any(w in text for w in words):
                    q_clips = [c for c in clips if any(w in f"{c.get('headline','')} {c.get('description','')}".lower() for w in words)]
                    if q_clips:
                        matched = q_clips
                    break
            pool = matched or clips
            selected = pool if matched else _spread(clips, target)
            if matched and budget_hint:
                selected = _spread(matched, target) if len(matched) > 3 else matched
            result = {
                "action": "reel",
                "title": (body.prompt[:60] or "Custom reel"),
                "focus": body.prompt[:60],
                "clips": [_public_clip(c) for c in selected],
            }

    if result["action"] == "ask":
        return {"game_id": game_id, "action": "ask", "question": result["question"], "source": source}

    reel_clips = _attach_overlays(result["clips"], facts)
    total = sum(c["duration"] for c in reel_clips)
    voice_script, voice_source = _voice_script(facts, reel_clips, target)
    return {
        "game_id": game_id,
        "action": "reel",
        "prompt": body.prompt,
        "reel": {
            "title": result["title"],
            "focus": result.get("focus"),
            "clip_count": len(reel_clips),
            "duration_seconds": total,
            "clips": reel_clips,
            "voice_script": voice_script,
            "voice_source": voice_source,
        },
        "note": f"Built a {max(1, round(total / 60))}-minute reel from {len(reel_clips)} real clips: {result['title']}",
        "source": source,
    }
