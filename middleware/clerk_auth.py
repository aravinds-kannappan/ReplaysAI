"""
Clerk JWT verification middleware for FastAPI.
Verifies the Bearer token from Clerk against their JWKS endpoint.
"""
import json
from typing import Optional

import httpx
import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from config import get_settings
from db.models import User
from db.session import get_db

_jwks_cache: Optional[dict] = None
security = HTTPBearer(auto_error=False)


async def _get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    settings = get_settings()
    # Derive JWKS URL from publishable key domain
    async with httpx.AsyncClient() as client:
        r = await client.get("https://api.clerk.com/v1/jwks", timeout=10)
        r.raise_for_status()
        _jwks_cache = r.json()
    return _jwks_cache


def _verify_clerk_token(token: str) -> dict:
    """Verify Clerk JWT and return payload. Raises HTTPException on failure."""
    try:
        # Clerk tokens are RS256 signed; decode header to get kid
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")

        # Use PyJWT's PyJWKClient for key fetching
        from jwt import PyJWKClient
        jwks_client = PyJWKClient("https://api.clerk.com/v1/jwks")
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: verify Clerk JWT → return User from DB."""
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = _verify_clerk_token(credentials.credentials)
    clerk_id: str = payload.get("sub", "")

    if not clerk_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No subject in token")

    user = db.query(User).filter_by(clerk_id=clerk_id).first()
    if not user:
        # Auto-create user on first authenticated request
        user = User(
            clerk_id=clerk_id,
            email=payload.get("email", ""),
            display_name=payload.get("name", ""),
        )
        db.add(user)
        db.flush()
        # Initialize points + streaks
        from db.models import UserPoints, UserStreak
        db.add(UserPoints(user_id=user.id))
        db.add(UserStreak(user_id=user.id))
        db.commit()
        db.refresh(user)

    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Like get_current_user but returns None instead of 401 for unauthenticated requests."""
    if not credentials:
        return None
    try:
        return get_current_user(credentials, db)
    except HTTPException:
        return None
