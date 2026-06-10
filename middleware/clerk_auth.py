"""
Clerk JWT verification for FastAPI without a database dependency.
"""
from dataclasses import dataclass
from typing import Optional

import jwt
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

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


def _verify_clerk_token(token: str) -> dict:
    """Verify Clerk JWT and return payload. Raises HTTPException on failure."""
    try:
        from jwt import PyJWKClient

        jwks_client = PyJWKClient("https://api.clerk.com/v1/jwks")
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
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


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> AuthUser:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return _user_from_payload(_verify_clerk_token(credentials.credentials))


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Optional[AuthUser]:
    if not credentials:
        return None
    try:
        return _user_from_payload(_verify_clerk_token(credentials.credentials))
    except HTTPException:
        return None
