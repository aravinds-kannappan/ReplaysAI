"""Lightweight waitlist capture.

No database is required for the free demo. Emails are accepted, lightly
validated, and logged so they show up in serverless logs; the source of truth
for an interested fan is still their own browser. Wire this to a durable store
or an email provider later without changing the frontend contract.
"""
import re

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["waitlist"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class WaitlistBody(BaseModel):
    email: str
    source: str | None = None


@router.post("/waitlist")
def join_waitlist(body: WaitlistBody):
    email = (body.email or "").strip()
    if not _EMAIL_RE.match(email):
        return {"status": "invalid", "message": "Enter a valid email address."}
    print(f"[waitlist] joined: {email} (source={body.source or 'landing'})")
    return {"status": "ok", "message": "You're on the list. We'll be in touch."}
