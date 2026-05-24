"""
Rate limiting middleware.

Uses slowapi (in-process token bucket) to cap how many expensive LLM
calls a single user can fire per minute.

Limits:
  - per IP:  60 req/min global default
  - per user: 30 chat messages / hour (the heavy LLM endpoint)
  - per user:  6 task starts / hour

Override via env vars: RATE_GLOBAL, RATE_CHAT, RATE_TASK
"""
from __future__ import annotations

import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _user_or_ip(request: Request) -> str:
    """Use authenticated user id when present, else fall back to IP."""
    user = getattr(request.state, "user", None)
    if user and isinstance(user, dict):
        uid = user.get("id") or user.get("sub")
        if uid:
            return f"user:{uid}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(
    key_func=_user_or_ip,
    default_limits=[os.environ.get("RATE_GLOBAL", "60/minute")],
)

# Per-endpoint convenience strings
RATE_CHAT = os.environ.get("RATE_CHAT", "30/hour")
RATE_TASK = os.environ.get("RATE_TASK", "6/hour")
RATE_AUTH = os.environ.get("RATE_AUTH", "10/minute")
