"""
Deterministic play-analysis agents.

IMPORTANT — these are NOT trained models. There is no training loop, dataset,
eval suite, or saved model artifact behind them. Each "agent" is a pure,
rule-based module that turns one play + its game context into a structured read,
plus a few transparent statistical proxies (field-goal make probability,
expected points, a win-probability proxy) computed from published heuristics.

The interface is intentionally stable — every agent implements
`analyze(ctx: PlayContext) -> AgentRead` — so a learned model can later replace
any single agent's implementation without changing the callers or the API shape.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Optional, Protocol


# ── Inputs / outputs ────────────────────────────────────────────────────────────
@dataclass
class PlayContext:
    sport: str
    play_type: str
    description: str
    period: int
    clock: Optional[str]
    away_abbr: str
    home_abbr: str
    away_score: int
    home_score: int
    prev_away: int
    prev_home: int
    kicking_team: Optional[str] = None   # abbr of the team that scored / is acting
    fg_distance: Optional[int] = None
    yards_to_goal: Optional[int] = None

    @property
    def score_delta(self) -> int:
        return (self.away_score + self.home_score) - (self.prev_away + self.prev_home)

    @property
    def margin_after(self) -> int:
        """Signed margin from the acting team's perspective (+ = acting team ahead)."""
        if self.kicking_team == self.away_abbr:
            return self.away_score - self.home_score
        return self.home_score - self.away_score


@dataclass
class AgentRead:
    agent: str
    headline: str
    detail: str
    metric_label: Optional[str] = None
    metric_value: Optional[str] = None


class PlayAgent(Protocol):
    name: str
    def analyze(self, ctx: PlayContext) -> AgentRead: ...


# ── Transparent statistical proxies (heuristics, not learned) ───────────────────
def fg_make_probability(distance: Optional[int]) -> float:
    """Logistic approximation of NFL field-goal make rate by distance. Heuristic
    eyeballed to public make-rate curves (~99% at 20y, ~80% at 45y, ~50% at 53y)."""
    if not distance:
        return 0.0
    return 1.0 / (1.0 + math.exp((distance - 53.5) / 6.5))


def seconds_remaining(period: int, clock: Optional[str], sport: str) -> int:
    quarter = 15 * 60 if sport.upper() == "NFL" else 12 * 60
    in_quarter = 0
    if clock and ":" in clock:
        try:
            mm, ss = (int(x) for x in clock.split(":")[:2])
            in_quarter = mm * 60 + ss
        except ValueError:
            in_quarter = 0
    return max(0, (4 - min(period, 4)) * quarter + in_quarter)


def win_probability(margin: int, secs_left: int, sport: str) -> float:
    """Time-decayed logistic on score margin — a WP *proxy*, not a trained model.
    Margin matters more as time runs out."""
    total = (4 * 15 * 60) if sport.upper() == "NFL" else (4 * 12 * 60)
    frac_left = max(0.02, secs_left / total)
    scale = 7.0 * math.sqrt(frac_left)
    return 1.0 / (1.0 + math.exp(-margin / max(0.5, scale)))


_POINTS = {"touchdown": 7, "field_goal": 3, "safety": 2}


def _ordinal_quarter(period: int) -> str:
    return {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}.get(period, f"OT{max(0, period - 4)}".rstrip("0") or "OT")


def _nba_shot(desc: str) -> dict:
    d = desc or ""
    dist = re.search(r"(\d{1,2})-foot", d)
    assist = re.search(r"\(([A-Za-z.'\- ]+?)\s+assists?\)", d)
    shooter = re.match(r"\s*([A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+)?)", d)
    return {
        "made": "makes" in d.lower(),
        "distance": int(dist.group(1)) if dist else None,
        "assist": assist.group(1).strip() if assist else None,
        "shooter": shooter.group(1).strip() if shooter else None,
    }


def _nba_shot_kind(play_type: str, desc: str) -> str:
    if play_type == "three_pointer":
        return "three"
    if play_type == "dunk":
        return "dunk"
    if "layup" in (desc or "").lower():
        return "layup"
    return "jumper"


# ── Agents ──────────────────────────────────────────────────────────────────────
class ScoutAgent:
    """Reads alignment / field position from the play type and spot."""
    name = "Scout"

    def analyze(self, ctx: PlayContext) -> AgentRead:
        if ctx.sport.upper() == "NBA":
            if ctx.play_type in ("steal", "block"):
                verb = "Steal" if ctx.play_type == "steal" else "Block"
                return AgentRead("Scout", verb, f"{verb} — the defense reads the play and flips possession.", "Read", "defense")
            info = _nba_shot(ctx.description)
            kind = _nba_shot_kind(ctx.play_type, ctx.description)
            feed = f"{info['assist']} sets it up — " if info["assist"] else ""
            spot = f"from {info['distance']} feet" if info["distance"] else ("at the rim" if kind in ("dunk", "layup") else "off the dribble")
            return AgentRead("Scout", f"{kind.title()} look",
                f"{feed}{info['shooter'] or 'The shooter'} gets the {kind} {spot}. The defense was a step late closing out.",
                "Read", "shot creation")
        if ctx.play_type == "field_goal":
            dist = f"{ctx.fg_distance}-yard try" if ctx.fg_distance else "field-goal try"
            return AgentRead(
                "Scout",
                "Field-goal unit on",
                f"{ctx.kicking_team or 'The offense'} sends out the field-goal team for a {dist}. "
                "Snapper over the ball, holder at ~7 yards, kicker stepping into the plant. "
                "Defense shows interior push to crowd the middle.",
                "Look", "FG protection vs. middle rush",
            )
        if ctx.play_type == "touchdown":
            return AgentRead("Scout", "Into the end zone",
                f"{ctx.kicking_team or 'The offense'} finishes the drive for six. The spacing held long "
                "enough to win the matchup at the goal line.", "Look", "Red-zone spacing")
        if ctx.play_type in ("interception", "turnover"):
            return AgentRead("Scout", "Takeaway", "Coverage jumped the route and flipped possession.",
                "Look", "Coverage shell")
        if ctx.play_type == "sack":
            return AgentRead("Scout", "Pressure home", "The rush won its one-on-one before the route concept developed.",
                "Look", "Protection breakdown")
        return AgentRead("Scout", "Field position", f"{ctx.kicking_team or 'The offense'} moves the chains.",
            "Look", "Down & distance")


class StatAgent:
    """The numbers: points added and (for kicks) the make-probability proxy."""
    name = "Stat"

    def analyze(self, ctx: PlayContext) -> AgentRead:
        if ctx.sport.upper() == "NBA":
            if ctx.play_type in ("steal", "block"):
                return AgentRead("Stat", "Possession swing", "No points on the play, but a stop that turns into offense the other way.", "Impact", "takeaway")
            info = _nba_shot(ctx.description)
            pts = abs(ctx.score_delta) or (3 if ctx.play_type == "three_pointer" else 2)
            dist = f"{info['distance']}-footer · " if info["distance"] else ""
            return AgentRead("Stat", f"{pts} points",
                f"{dist}scoreboard now {ctx.away_abbr} {ctx.away_score}, {ctx.home_abbr} {ctx.home_score}.",
                "Points", str(pts))
        pts = abs(ctx.score_delta) or _POINTS.get(ctx.play_type, 0)
        if ctx.play_type == "field_goal" and ctx.fg_distance:
            p = fg_make_probability(ctx.fg_distance)
            return AgentRead("Stat", f"{ctx.fg_distance} yards · {pts} points",
                f"From {ctx.fg_distance}, the make-rate proxy is about {round(p * 100)}%. "
                f"Scoreboard now {ctx.away_abbr} {ctx.away_score}, {ctx.home_abbr} {ctx.home_score}.",
                "Make prob (proxy)", f"{round(p * 100)}%")
        return AgentRead("Stat", f"{pts} points on the board" if pts else "No points",
            f"Scoreboard now {ctx.away_abbr} {ctx.away_score}, {ctx.home_abbr} {ctx.home_score}.",
            "Points added", str(pts))


class RefAgent:
    """Rules/officiating context for the play type. Rule-based, no replay access."""
    name = "Ref"

    def analyze(self, ctx: PlayContext) -> AgentRead:
        if ctx.sport.upper() == "NBA":
            d = ctx.description.lower()
            if "and" in d and ("foul" in d or "free throw" in d):
                return AgentRead("Ref", "And-one", "Contact on the shot — continuation ruled, basket counts and a free throw is coming.", "Rule", "Continuation")
            return AgentRead("Ref", "Clean bucket", "No whistle on the play; the basket counts as released.", "Rule", "No foul")
        if ctx.play_type == "field_goal":
            return AgentRead("Ref", "Live ball on the kick",
                "A field goal is a live ball: if it's short or blocked the defense can advance it, and "
                "the kick must clear the rush and stay inside the uprights. No flags on the attempt.",
                "Rule", "Scrimmage-kick / live ball")
        if ctx.play_type == "touchdown":
            return AgentRead("Ref", "Score subject to review",
                "Scoring plays are automatically reviewed — possession, the goal-line break, and feet "
                "in bounds are checked before the points stand.", "Rule", "Automatic booth review")
        if ctx.play_type == "interception":
            return AgentRead("Ref", "Change of possession",
                "Interception return is live; the spot is where the runner is down or steps out.",
                "Rule", "Live return")
        return AgentRead("Ref", "Clean play", "No officiating flag or review indicated on this play.",
            "Rule", "No flag")


class PredictAgent:
    """Expected-points and win-probability *proxies* for the play's swing."""
    name = "Predict"

    def analyze(self, ctx: PlayContext) -> AgentRead:
        secs = seconds_remaining(ctx.period, ctx.clock, ctx.sport)
        margin_before = ctx.margin_after - (ctx.score_delta if ctx.kicking_team in (ctx.away_abbr, ctx.home_abbr) else 0)
        wp_before = win_probability(margin_before, secs, ctx.sport)
        wp_after = win_probability(ctx.margin_after, secs, ctx.sport)
        swing = round((wp_after - wp_before) * 100)
        return AgentRead("Predict", f"Win-prob proxy {'+' if swing >= 0 else ''}{swing} pts",
            f"For {ctx.kicking_team or 'the scoring team'}, the proxy moves from ~{round(wp_before * 100)}% "
            f"to ~{round(wp_after * 100)}% with {ctx.clock or '—'} left in the {_ordinal_quarter(ctx.period)}.",
            "WP proxy (after)", f"{round(wp_after * 100)}%")


_AGENTS: list[PlayAgent] = [ScoutAgent(), StatAgent(), RefAgent(), PredictAgent()]


# ── Top-level analysis ──────────────────────────────────────────────────────────
def _why_it_mattered(ctx: PlayContext) -> str:
    secs = seconds_remaining(ctx.period, ctx.clock, ctx.sport)
    late = secs <= 5 * 60 and ctx.period >= 4
    pts = abs(ctx.score_delta) or _POINTS.get(ctx.play_type, 0)
    margin = abs(ctx.margin_after)
    if late and margin <= 8:
        return f"Late and close — these {pts} points swing a one-score game in the {_ordinal_quarter(ctx.period)}."
    if margin <= 3:
        return f"Keeps it a one-possession game; every score is now leverage."
    if pts >= 6:
        return f"A {pts}-point answer that reshapes the margin and the time/score math."
    return f"Extends the margin and forces the trailing side to respond."


def parse_fg_distance(description: str) -> Optional[int]:
    m = re.search(r"(\d{1,2})\s*[- ]?\s*yard(?:s)?\s+field goal", description or "", re.I)
    return int(m.group(1)) if m else None


def analyze_play(ctx: PlayContext) -> dict:
    """Full derived analysis for a single play. Pure and deterministic."""
    secs = seconds_remaining(ctx.period, ctx.clock, ctx.sport)
    pts = abs(ctx.score_delta) or _POINTS.get(ctx.play_type, 0)
    p_make = fg_make_probability(ctx.fg_distance) if ctx.play_type == "field_goal" else None
    ep_before = round((p_make or 0) * 3, 2) if ctx.play_type == "field_goal" else None

    field_position = None
    if ctx.fg_distance:
        field_position = f"{ctx.fg_distance}-yard attempt"
        if ctx.yards_to_goal is not None:
            field_position += f" — line of scrimmage ~{ctx.yards_to_goal} from the goal line"

    margin_before = ctx.margin_after - (pts if ctx.score_delta else 0)
    wp_before = win_probability(margin_before, secs, ctx.sport)
    wp_after = win_probability(ctx.margin_after, secs, ctx.sport)

    return {
        "score_impact": {
            "points": pts,
            "new_score": {"away": ctx.away_score, "home": ctx.home_score},
            "label": f"{ctx.away_abbr} {ctx.away_score} · {ctx.home_abbr} {ctx.home_score}",
        },
        "clock_context": f"{_ordinal_quarter(ctx.period)} quarter, {ctx.clock or '—'} on the clock"
                         + (" · under five minutes" if secs <= 5 * 60 and ctx.period >= 4 else ""),
        "field_position": field_position,
        "expected_points": None if ep_before is None else {
            "attempt": ep_before, "scored": pts, "make_prob": round((p_make or 0), 3),
            "label": f"~{ep_before} expected pts on the try (make-rate proxy {round((p_make or 0) * 100)}%)",
        },
        "win_prob": {
            "before": round(wp_before, 3), "after": round(wp_after, 3),
            "delta_pct": round((wp_after - wp_before) * 100),
            "label": f"~{round(wp_before * 100)}% → ~{round(wp_after * 100)}% (proxy)",
        },
        "why_it_mattered": _why_it_mattered(ctx),
        "agents": [vars(agent.analyze(ctx)) for agent in _AGENTS],
        "disclaimer": "Analysis is rule-based and statistical (deterministic proxies), not a trained model.",
    }
