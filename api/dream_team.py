"""Dream Team — server-side Monte Carlo championship simulation.

A user assembles an all-star roster (real NBA/NFL players). We:

1. Build a rating vector for each player from REAL ESPN season stats.
2. Ask a CoachAgent (LLM, with a deterministic fallback) for a fit/chemistry
   modifier and a one-line read.
3. Run a 10k-season Monte Carlo: each season draws form noise, simulates a win
   total, playoff seeding, and a round-by-round bracket.
4. Ask an AnalystAgent (LLM, with a templated fallback) for the X-factor blurb.

NOTHING here is a real result: the odds/record/playoff distribution are an
explicit forecast computed from real player ratings. The player names and stats
are real ESPN data.
"""
import hashlib
import json
import math
import random
import re

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.espn_public import (
    _athlete_team_abbr,
    _fetch_byathlete_pages,
    _flatten_athlete_stats,
    _star_score,
)
from api.recaps import llm_text
from cache.redis_client import cache_get, cache_set
from config import get_settings

router = APIRouter(prefix="/api/dream-team", tags=["dream-team"])

SIM_TTL = 6 * 3600
DEFAULT_ITERATIONS = 10_000
MAX_ITERATIONS = 20_000

# Games in a regular season, and a star-score divisor that maps an elite player
# to ~95 overall and a rotation player to the 50s.
_LEAGUE = {
    "NBA": {"games": 82, "divisor": 3.7, "playoff_cut": 0.52},
    "NFL": {"games": 17, "divisor": 5.0, "playoff_cut": 0.56},
}

ROUND_LABELS = ["miss", "r1", "r2", "conf", "finals", "champ"]


class PlayerHint(BaseModel):
    id: int
    name: str | None = None
    position: str | None = None


class SimRequest(BaseModel):
    sport: str
    player_ids: list[int] = Field(default_factory=list)
    players: list[PlayerHint] = Field(default_factory=list)
    iterations: int | None = None


def _signature(sport: str, ids: list[int], iterations: int) -> str:
    raw = f"{sport}|{sorted(set(ids))}|{iterations}"
    return "dreamteam:" + hashlib.sha1(raw.encode()).hexdigest()[:16]


def _overall(sport: str, raw_score: float) -> int:
    divisor = _LEAGUE[sport]["divisor"]
    return max(40, min(99, round(40 + raw_score / divisor)))


def _vector(sport: str, flat: dict[str, float]) -> dict[str, int]:
    """A small, display-friendly 0-100 rating vector for the result card."""
    def clamp(v: float) -> int:
        return max(20, min(99, round(v)))

    if sport == "NBA":
        return {
            "offense": clamp(40 + float(flat.get("avgPoints", 0)) * 2.0),
            "playmaking": clamp(45 + float(flat.get("avgAssists", 0)) * 6.0),
            "defense": clamp(
                45 + float(flat.get("avgSteals", 0)) * 9.0 + float(flat.get("avgBlocks", 0)) * 8.0
            ),
            "efficiency": clamp(
                45 + float(flat.get("avgRebounds", 0)) * 2.4 + float(flat.get("avgPoints", 0)) * 0.6
            ),
        }
    offense = (
        float(flat.get("passingYards", 0)) * 0.012
        + float(flat.get("passingTouchdowns", 0)) * 2.0
        + float(flat.get("rushingYards", 0)) * 0.05
        + float(flat.get("receivingYards", 0)) * 0.05
        + (float(flat.get("rushingTouchdowns", 0)) + float(flat.get("receivingTouchdowns", 0))) * 3.0
    )
    defense = (
        float(flat.get("totalTackles", 0)) * 0.5
        + float(flat.get("sacks", 0)) * 5.0
        + float(flat.get("interceptions", 0)) * 6.0
    )
    return {
        "offense": clamp(45 + offense),
        "defense": clamp(45 + defense),
        "playmaking": clamp(45 + offense * 0.6),
        "efficiency": clamp(50 + (offense + defense) * 0.25),
    }


def _build_roster(sport: str, ids: list[int], hints: list[PlayerHint]) -> list[dict]:
    """Real ESPN ratings for the requested athlete ids. Players missing from the
    leaderboard get a baseline so the sim still runs."""
    want = {int(i) for i in ids}
    hint_by_id = {h.id: h for h in hints}
    flat_by_id: dict[int, dict] = {}
    athlete_by_id: dict[int, dict] = {}
    try:
        athletes, names_by_cat = _fetch_byathlete_pages(sport)
        for item in athletes:
            athlete = item.get("athlete") or {}
            aid = athlete.get("id")
            if not aid or int(aid) not in want:
                continue
            flat_by_id[int(aid)] = _flatten_athlete_stats(item, names_by_cat)
            athlete_by_id[int(aid)] = athlete
    except Exception:
        pass

    roster: list[dict] = []
    for pid in ids:
        hint = hint_by_id.get(pid)
        athlete = athlete_by_id.get(pid, {})
        flat = flat_by_id.get(pid, {})
        position = (
            (athlete.get("position") or {}).get("abbreviation")
            or (hint.position if hint else None)
            or ""
        )
        if flat:
            raw = _star_score(sport, {"position": position}, flat)
            overall = _overall(sport, raw)
            vector = _vector(sport, flat)
            rated = True
        else:
            # No published season line — a neutral-but-credible baseline.
            overall = 62
            vector = {"offense": 60, "defense": 60, "playmaking": 60, "efficiency": 60}
            rated = False
        roster.append({
            "id": pid,
            "name": athlete.get("displayName") or (hint.name if hint else None) or f"Player {pid}",
            "team": _athlete_team_abbr(athlete) or None,
            "position": position or None,
            "overall": overall,
            "vector": vector,
            "rated": rated,
        })
    roster.sort(key=lambda p: p["overall"], reverse=True)
    return roster


def _fallback_chemistry(sport: str, roster: list[dict]) -> dict:
    """Positional balance rewards variety; an all-offense star stack gets a small
    usage penalty. Returns a multiplier in ~[0.86, 1.12]."""
    if not roster:
        return {"multiplier": 1.0, "read": "Add players to assess chemistry.", "generated_by": "fallback"}
    positions = [p.get("position") or "?" for p in roster]
    variety = len({p for p in positions if p != "?"})
    mods = 1.0
    if sport == "NBA":
        mods += min(variety, 5) * 0.012  # spacing across positions
        high_usage = sum(1 for p in roster if p["vector"]["offense"] >= 85)
        if high_usage >= 3:
            mods -= (high_usage - 2) * 0.03  # too many ball-dominant scorers
        defense = sum(p["vector"]["defense"] for p in roster) / len(roster)
        mods += (defense - 60) / 600
    else:
        has_qb = any((p.get("position") or "").upper() == "QB" for p in roster)
        mods += 0.05 if has_qb else -0.06
        mods += min(variety, 6) * 0.01
    multiplier = max(0.86, min(1.12, mods))
    read = (
        "Balanced fit across positions." if multiplier >= 1.0
        else "Overlapping roles may cap the ceiling."
    )
    return {"multiplier": round(multiplier, 3), "read": read, "generated_by": "fallback"}


def _coach_chemistry(sport: str, roster: list[dict]) -> dict:
    """CoachAgent: an LLM fit/chemistry read, falling back to the heuristic."""
    settings = get_settings()
    fallback = _fallback_chemistry(sport, roster)
    if not settings.anthropic_api_key and not settings.openai_api_key:
        return fallback

    lines = "\n".join(
        f"- {p['name']} ({p.get('position') or '?'}, {p.get('team') or 'FA'}): overall {p['overall']}, "
        f"off {p['vector']['offense']} / def {p['vector']['defense']} / playmk {p['vector']['playmaking']}"
        for p in roster
    )
    raw = llm_text(
        system=(
            "You are ReplaysAI's CoachAgent. Judge the FIT and CHEMISTRY of an all-star "
            f"{sport} roster: positional balance, spacing/role overlap, two-way balance. "
            "Return ONLY JSON: {\"multiplier\": <0.86-1.12>, \"read\": \"<one sentence>\"}. "
            "1.0 is neutral; reward complementary fits, penalize redundant ball-dominant stars."
        ),
        prompt=f"Roster:\n{lines}\n\nReturn the JSON only.",
        max_tokens=200,
    )
    if not raw:
        return fallback
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return fallback
    try:
        parsed = json.loads(match.group(0))
        mult = float(parsed.get("multiplier"))
        read = str(parsed.get("read") or fallback["read"]).strip()
        if not 0.7 <= mult <= 1.25:
            return fallback
        return {"multiplier": round(mult, 3), "read": read, "generated_by": "anthropic"}
    except Exception:
        return fallback


def _simulate(sport: str, roster: list[dict], chemistry: float, iterations: int) -> dict:
    """Monte Carlo over `iterations` seasons. Strength is the chemistry-weighted
    mean of the roster's best players, mapped to per-game and per-round win
    probabilities; each season draws form noise."""
    games = _LEAGUE[sport]["games"]
    cut = _LEAGUE[sport]["playoff_cut"]
    if not roster:
        return {
            "championship_odds_pct": 0.0,
            "projected_record": {"wins": 0, "losses": games},
            "playoff_round_distribution": {k: 0 for k in ROUND_LABELS},
            "avg_seed": None,
        }

    # Weight the top of the roster more; a star core drives outcomes.
    top = sorted((p["overall"] for p in roster), reverse=True)
    weights = [1.0, 0.85, 0.7, 0.6, 0.5, 0.42, 0.36, 0.3]
    paired = list(zip(top, weights))
    base = sum(o * w for o, w in paired) / sum(w for _, w in paired[: len(top)])
    # Center a league-average overall (~65) at strength 0.5, then apply chemistry
    # to the delta from average so an elite core is dominant but believable.
    strength = 0.5 + (base - 65) * 0.0135
    strength = 0.5 + (strength - 0.5) * chemistry
    strength = max(0.08, min(0.95, strength))

    dist = {k: 0 for k in ROUND_LABELS}
    total_wins = 0
    seed_sum = 0.0
    seed_n = 0
    rng = random.Random(12345)  # deterministic across identical rosters

    for _ in range(iterations):
        form = rng.gauss(0, 0.06)
        eff = max(0.04, min(0.97, strength + form))
        p_game = max(0.12, min(0.90, 0.5 + (eff - 0.5) * 0.9))
        # Normal approximation to the season win total.
        mean = games * p_game
        sd = math.sqrt(games * p_game * (1 - p_game))
        wins = round(min(games, max(0, rng.gauss(mean, sd))))
        total_wins += wins
        win_pct = wins / games

        if win_pct < cut * (0.9 + rng.random() * 0.2):
            dist["miss"] += 1
            continue

        # Seed quality (1 best) feeds a small bracket advantage.
        seed = max(1, min(8, round(8 - (win_pct - cut) / max(1e-6, (0.95 - cut)) * 7)))
        seed_sum += seed
        seed_n += 1
        p_round = max(0.2, min(0.82, 0.5 + (eff - 0.5) * 1.0 - (seed - 1) * 0.012))

        reached = "r1"
        for round_idx, label in enumerate(["r1", "r2", "conf", "finals"]):
            # Later rounds face tougher fields.
            p = max(0.18, p_round - round_idx * 0.03)
            if rng.random() <= p:
                reached = "champ" if label == "finals" else ["r2", "conf", "finals", "champ"][round_idx]
            else:
                reached = label
                break
        dist[reached] += 1

    return {
        "championship_odds_pct": round(dist["champ"] / iterations * 100, 1),
        "projected_record": {
            "wins": round(total_wins / iterations),
            "losses": games - round(total_wins / iterations),
        },
        "playoff_round_distribution": dist,
        "avg_seed": round(seed_sum / seed_n, 1) if seed_n else None,
        "strength": round(strength, 3),
    }


def _analyst_blurb(sport: str, roster: list[dict], sim: dict, chemistry: dict) -> dict:
    settings = get_settings()
    star = roster[0] if roster else None
    odds = sim["championship_odds_pct"]
    rec = sim["projected_record"]
    fallback = (
        f"This squad projects to a {rec['wins']}-{rec['losses']} season and a {odds}% title shot. "
        + (f"{star['name']} is the engine — " if star else "")
        + (
            "the X-factor is two-way balance: keep the defense honest and the ceiling is real."
            if chemistry["multiplier"] >= 1.0
            else "the X-factor is role clarity: someone has to sacrifice usage for the fit to click."
        )
    )
    if not settings.anthropic_api_key and not settings.openai_api_key:
        return {"blurb": fallback, "generated_by": "fallback"}

    names = ", ".join(p["name"] for p in roster[:8])
    text = llm_text(
        system=(
            "You are ReplaysAI's AnalystAgent. In 2-3 sentences, call out the single X-FACTOR "
            "that decides this all-star roster's title run. Ground it ONLY in the supplied "
            "projection and ratings. Do not invent stats or real results. Confident, broadcast tone."
        ),
        prompt=(
            f"{sport} roster: {names}.\n"
            f"Projection: {rec['wins']}-{rec['losses']} record, {odds}% championship odds, "
            f"coach chemistry read: {chemistry['read']} (x{chemistry['multiplier']}).\n"
            f"Top-rated player: {star['name'] if star else 'n/a'}.\n\nWrite the X-factor."
        ),
        max_tokens=220,
    )
    return {"blurb": text.strip(), "generated_by": "anthropic"} if text else {"blurb": fallback, "generated_by": "fallback"}


@router.post("/simulate")
def simulate(body: SimRequest):
    sport = body.sport.upper()
    if sport not in _LEAGUE:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="sport must be NBA or NFL")
    ids = [int(i) for i in body.player_ids][:12]
    iterations = max(1000, min(MAX_ITERATIONS, body.iterations or DEFAULT_ITERATIONS))

    if not ids:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="Pick at least one player.")

    sig = _signature(sport, ids, iterations)
    cached = cache_get(sig)
    if cached:
        return {**cached, "cached": True}

    roster = _build_roster(sport, ids, body.players)
    chemistry = _coach_chemistry(sport, roster)
    sim = _simulate(sport, roster, chemistry["multiplier"], iterations)
    x_factor = _analyst_blurb(sport, roster, sim, chemistry)

    result = {
        "sport": sport,
        "iterations": iterations,
        "roster": [
            {"id": p["id"], "name": p["name"], "team": p["team"], "position": p["position"],
             "overall": p["overall"], "vector": p["vector"], "rated": p["rated"]}
            for p in roster
        ],
        "chemistry": chemistry,
        "championship_odds_pct": sim["championship_odds_pct"],
        "projected_record": sim["projected_record"],
        "playoff_round_distribution": sim["playoff_round_distribution"],
        "avg_seed": sim["avg_seed"],
        "x_factor": x_factor,
        "generated_by": x_factor["generated_by"],
        "cached": False,
    }
    cache_set(sig, result, ttl=SIM_TTL)
    return result
