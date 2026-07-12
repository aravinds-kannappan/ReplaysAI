"""
Durable, login-free store for a fan's picks, points, and leaderboard rank.

Keyed by the anonymous device id (see middleware/identity.py) and backed by
Redis (Upstash / Vercel KV via REDIS_URL, reusing cache/redis_client.py). This
is the "light datastore" that makes picks, gamification, and the leaderboard
real instead of decorative.

When REDIS_URL is not configured, every function degrades to a no-op / empty
result so local dev and the zero-config demo still run: picks just do not
persist and the leaderboard is empty. Nothing in the request path hard-fails on
a missing or unreachable store.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Optional

from cache.redis_client import get_redis
from config import get_settings

POINTS_CORRECT = 10
LEADERBOARD_KEY = "leaderboard:points"
_NEWSLETTER_TTL = 60 * 60 * 24 * 120  # 120 days


def store_enabled() -> bool:
    return bool(get_settings().redis_url)


def _picks_key(device_id: str) -> str:
    return f"picks:{device_id}"


def _profile_key(device_id: str) -> str:
    return f"profile:{device_id}"


def _newsletter_key(token: str) -> str:
    return f"newsletter:{token}"


def _fallback_handle(device_id: str) -> str:
    """A stable, anonymous public handle derived from the device id. No PII: the
    device id is meaningless outside the fan's own browser."""
    h = hashlib.sha1(device_id.encode()).hexdigest()[:4].upper()
    return f"Fan-{h}"


# ── picks ────────────────────────────────────────────────────────────────────

def save_pick(device_id: str, game_id: int, team_id: int,
              sport: str | None = None, game_date: str | None = None) -> dict:
    """Store (or update, while still unresolved) a fan's pick for a game."""
    pick = {
        "game_id": game_id,
        "predicted_winner_team_id": team_id,
        "sport": sport,
        "game_date": game_date,
        "created_at": time.time(),
        "resolved": False,
        "resolved_at": None,
        "is_correct": None,
        "points_earned": 0,
    }
    if not store_enabled():
        return pick
    try:
        r = get_redis()
        existing = r.hget(_picks_key(device_id), str(game_id))
        if existing:
            prev = json.loads(existing)
            # A resolved pick is locked: never let a re-pick rewrite history.
            if prev.get("resolved"):
                return prev
            pick["created_at"] = prev.get("created_at", pick["created_at"])
        r.hset(_picks_key(device_id), str(game_id), json.dumps(pick))
        _ensure_profile(device_id)
    except Exception:
        pass
    return pick


def get_pick_map(device_id: str) -> dict[int, dict]:
    if not store_enabled():
        return {}
    try:
        raw = get_redis().hgetall(_picks_key(device_id))
        return {int(gid): json.loads(val) for gid, val in raw.items()}
    except Exception:
        return {}


def mark_resolved(device_id: str, game_id: int, is_correct: bool) -> int:
    """Resolve one pick exactly once. Awards points, updates the leaderboard and
    the fan's counters/streak. Returns points added (0 if already resolved)."""
    if not store_enabled():
        return 0
    try:
        r = get_redis()
        raw = r.hget(_picks_key(device_id), str(game_id))
        if not raw:
            return 0
        pick = json.loads(raw)
        if pick.get("resolved"):
            return 0
        points = POINTS_CORRECT if is_correct else 0
        pick.update({"resolved": True, "resolved_at": time.time(),
                     "is_correct": is_correct, "points_earned": points})
        r.hset(_picks_key(device_id), str(game_id), json.dumps(pick))

        # Counters + streak live in the profile hash; points also feed the
        # leaderboard sorted set (its authoritative score).
        pkey = _profile_key(device_id)
        r.hincrby(pkey, "total", 1)
        if is_correct:
            r.hincrby(pkey, "correct", 1)
            streak = r.hincrby(pkey, "streak", 1)
            best = int(r.hget(pkey, "best_streak") or 0)
            if streak > best:
                r.hset(pkey, "best_streak", streak)
            r.zincrby(LEADERBOARD_KEY, points, device_id)
        else:
            r.hset(pkey, "streak", 0)
        _ensure_profile(device_id)
        return points
    except Exception:
        return 0


# ── profile / gamification ───────────────────────────────────────────────────

def _ensure_profile(device_id: str) -> None:
    try:
        r = get_redis()
        pkey = _profile_key(device_id)
        if not r.exists(pkey):
            r.hset(pkey, mapping={"created_at": time.time(), "correct": 0, "total": 0, "streak": 0, "best_streak": 0})
        # Make sure every fan appears on the leaderboard, even at 0 points.
        if r.zscore(LEADERBOARD_KEY, device_id) is None:
            r.zadd(LEADERBOARD_KEY, {device_id: 0}, nx=True)
    except Exception:
        pass


def set_display_name(device_id: str, name: str) -> None:
    if not store_enabled() or not name:
        return
    try:
        get_redis().hset(_profile_key(device_id), "display_name", name.strip()[:40])
    except Exception:
        pass


def _badges(correct: int, total: int, best_streak: int) -> list[dict]:
    out: list[dict] = []
    if total >= 1:
        out.append({"slug": "rookie", "name": "First Pick", "icon": "🎯"})
    if correct >= 5:
        out.append({"slug": "sharp", "name": "Sharp (5 correct)", "icon": "📈"})
    if correct >= 15:
        out.append({"slug": "oracle", "name": "Oracle (15 correct)", "icon": "🔮"})
    if best_streak >= 3:
        out.append({"slug": "streak-3", "name": "Hot Streak (3)", "icon": "🔥"})
    if best_streak >= 5:
        out.append({"slug": "streak-5", "name": "On Fire (5)", "icon": "⚡"})
    return out


def get_profile(device_id: str) -> dict:
    """Real points/streak/badges for a device. Zeros when the store is off."""
    base = {
        "device_id": device_id, "display_name": None,
        "total_points": 0, "correct_predictions": 0, "total_predictions": 0,
        "prediction_accuracy": 0.0, "login_streak": 0, "best_streak": 0, "badges": [],
    }
    if not store_enabled():
        return base
    try:
        r = get_redis()
        prof = r.hgetall(_profile_key(device_id)) or {}
        points = r.zscore(LEADERBOARD_KEY, device_id) or 0
        correct = int(prof.get("correct", 0))
        total = int(prof.get("total", 0))
        best_streak = int(prof.get("best_streak", 0))
        base.update({
            "display_name": prof.get("display_name"),
            "total_points": int(points),
            "correct_predictions": correct,
            "total_predictions": total,
            "prediction_accuracy": round(correct / total, 3) if total else 0.0,
            "login_streak": int(prof.get("streak", 0)),
            "best_streak": best_streak,
            "badges": _badges(correct, total, best_streak),
        })
    except Exception:
        pass
    return base


# ── leaderboard ──────────────────────────────────────────────────────────────

def _row(device_id: str, points: float, rank: int) -> dict:
    prof = get_profile(device_id)
    name = prof["display_name"] or _fallback_handle(device_id)
    return {
        "rank": rank,
        "user_id": device_id,
        "display_name": name,
        "username": name,
        "avatar_url": None,
        "total_points": int(points),
        "correct_predictions": prof["correct_predictions"],
        "total_predictions": prof["total_predictions"],
        "accuracy": prof["prediction_accuracy"],
        "login_streak": prof["login_streak"],
        "badges": prof["badges"],
    }


def top_leaders(limit: int = 50) -> list[dict]:
    if not store_enabled():
        return []
    try:
        rows = get_redis().zrevrange(LEADERBOARD_KEY, 0, max(0, limit - 1), withscores=True)
        return [_row(dev, score, i + 1) for i, (dev, score) in enumerate(rows)]
    except Exception:
        return []


def rank_and_neighbors(device_id: str, window: int = 3) -> dict:
    prof = get_profile(device_id)
    me_row = {
        "rank": 1, "user_id": device_id,
        "display_name": prof["display_name"] or _fallback_handle(device_id),
        "username": prof["display_name"] or _fallback_handle(device_id),
        "avatar_url": None, "total_points": prof["total_points"],
        "correct_predictions": prof["correct_predictions"],
        "total_predictions": prof["total_predictions"],
        "accuracy": prof["prediction_accuracy"],
        "login_streak": prof["login_streak"], "badges": prof["badges"],
    }
    if not store_enabled():
        return {"my_rank": 1, "total_users": 1, "neighbors": [me_row]}
    try:
        r = get_redis()
        total_users = r.zcard(LEADERBOARD_KEY) or 1
        rank0 = r.zrevrank(LEADERBOARD_KEY, device_id)
        if rank0 is None:
            _ensure_profile(device_id)
            rank0 = r.zrevrank(LEADERBOARD_KEY, device_id) or 0
        lo = max(0, rank0 - window)
        hi = rank0 + window
        rows = r.zrevrange(LEADERBOARD_KEY, lo, hi, withscores=True)
        neighbors = [_row(dev, score, lo + i + 1) for i, (dev, score) in enumerate(rows)]
        return {"my_rank": rank0 + 1, "total_users": total_users, "neighbors": neighbors}
    except Exception:
        return {"my_rank": 1, "total_users": 1, "neighbors": [me_row]}


# ── newsletter share ─────────────────────────────────────────────────────────

def save_newsletter(token: str, payload: dict) -> bool:
    if not store_enabled() or not token:
        return False
    try:
        get_redis().setex(_newsletter_key(token), _NEWSLETTER_TTL, json.dumps(payload))
        return True
    except Exception:
        return False


def get_newsletter(token: str) -> Optional[dict]:
    if not store_enabled():
        return None
    try:
        raw = get_redis().get(_newsletter_key(token))
        return json.loads(raw) if raw else None
    except Exception:
        return None
