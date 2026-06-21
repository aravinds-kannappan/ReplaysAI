"""
Clerk JWT verification for FastAPI without a database dependency.
"""
import ssl
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import certifi
import jwt
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import get_settings

security = HTTPBearer(auto_error=False)


@dataclass
class AuthUser:
    id: str
    clerk_id: str
    username: str | None = None
    display_name: str | None = None
    email: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    favorite_teams: list[dict] | None = None
    followed_players: list[dict] | None = None


# Clerk's public JWKS lives on the instance's frontend-API domain
# (https://<instance>.clerk.accounts.dev/.well-known/jwks.json) — the
# api.clerk.com/v1/jwks endpoint requires a secret key and rejects PyJWKClient.
_jwks_clients: dict[str, "jwt.PyJWKClient"] = {}


def _trusted_issuer(token: str) -> str:
    settings_issuer = get_settings().clerk_issuer.rstrip("/")
    if settings_issuer:
        return settings_issuer
    payload = jwt.decode(token, options={"verify_signature": False})
    issuer = str(payload.get("iss") or "").rstrip("/")
    host = urlparse(issuer).hostname or ""
    # Without a configured issuer, only Clerk-hosted domains are trusted —
    # otherwise a forged iss claim could point verification at attacker keys.
    if not issuer.startswith("https://") or not host.endswith(".clerk.accounts.dev"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Untrusted token issuer; set CLERK_ISSUER for custom Clerk domains",
        )
    return issuer


def _verify_clerk_token(token: str) -> dict:
    """Verify Clerk JWT and return payload. Raises HTTPException on failure."""
    try:
        from jwt import PyJWKClient

        issuer = _trusted_issuer(token)
        jwks_client = _jwks_clients.get(issuer)
        if jwks_client is None:
            jwks_client = PyJWKClient(
                f"{issuer}/.well-known/jwks.json",
                ssl_context=ssl.create_default_context(cafile=certifi.where()),
            )
            _jwks_clients[issuer] = jwks_client
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"verify_aud": False},
        )
    except HTTPException:
        raise
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}")


def _user_from_payload(payload: dict) -> AuthUser:
    clerk_id = payload.get("sub", "")
    if not clerk_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No subject in token")
    return AuthUser(
        id=clerk_id,
        clerk_id=clerk_id,
        username=payload.get("username"),
        display_name=payload.get("name") or payload.get("full_name"),
        email=payload.get("email"),
        avatar_url=payload.get("picture"),
        favorite_teams=[],
        followed_players=[],
    )


def guest_user() -> AuthUser:
    """The app runs fully without login, so requests without a verifiable token
    resolve to an anonymous guest instead of being rejected."""
    return AuthUser(id="guest", clerk_id="guest", username="guest", display_name="Guest", favorite_teams=[], followed_players=[])


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> AuthUser:
    # No login is required anymore. If a token is present and valid we use it,
    # otherwise everyone is treated as an anonymous guest.
    if not credentials:
        return guest_user()
    try:
        return _user_from_payload(_verify_clerk_token(credentials.credentials))
    except HTTPException:
        return guest_user()


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Optional[AuthUser]:
    if not credentials:
        return None
    try:
        return _user_from_payload(_verify_clerk_token(credentials.credentials))
    except HTTPException:
        return None
