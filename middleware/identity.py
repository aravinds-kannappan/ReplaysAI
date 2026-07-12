"""
Anonymous device identity for FastAPI.

The app requires no login. A browser generates one UUID (stored in localStorage)
and sends it as the `X-Device-Id` header. That id is the durable key for a fan's
picks, points, and leaderboard rank in the Redis store (see `db/store.py`). When
no id is present (curl, health checks, a first paint before the client attaches
the header) the request resolves to an anonymous guest with no persistence.

This replaces the previous Clerk JWT middleware: there is no external auth
provider, no secret key, and no JWT verification in the request path.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Header


@dataclass
class AuthUser:
    id: str
    # `clerk_id` is retained only so response shapes that historically echoed it
    # keep working; it now mirrors the device id.
    clerk_id: str = ""
    device_id: str = ""
    username: str | None = None
    display_name: str | None = None
    email: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    favorite_teams: list[dict] | None = None
    followed_players: list[dict] | None = None

    @property
    def is_guest(self) -> bool:
        return not self.device_id


def _normalize(raw: str | None) -> str:
    """Accept only a sane device id. The client sends a UUID; reject empty or
    over-long junk so a bad header can never become a storage key."""
    dev = (raw or "").strip()
    if not dev or len(dev) > 64:
        return ""
    return dev


def guest_user() -> AuthUser:
    return AuthUser(
        id="guest", clerk_id="guest", device_id="",
        username="guest", display_name="Guest",
        favorite_teams=[], followed_players=[],
    )


def _device_user(dev: str) -> AuthUser:
    return AuthUser(
        id=dev, clerk_id=dev, device_id=dev,
        favorite_teams=[], followed_players=[],
    )


def get_current_user(x_device_id: Optional[str] = Header(default=None)) -> AuthUser:
    dev = _normalize(x_device_id)
    return _device_user(dev) if dev else guest_user()


def get_optional_user(x_device_id: Optional[str] = Header(default=None)) -> Optional[AuthUser]:
    dev = _normalize(x_device_id)
    return _device_user(dev) if dev else None
