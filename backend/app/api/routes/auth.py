"""Google OAuth2 login flow + JWT session tokens."""

from __future__ import annotations

import time
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from jose import jwt

from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def _make_jwt(email: str, name: str, picture: str) -> str:
    payload = {
        "sub": email,
        "email": email,
        "name": name,
        "picture": picture,
        "iat": int(time.time()),
        "exp": int(time.time()) + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


@router.get("/google/login")
async def google_login() -> RedirectResponse:
    """Redirect browser to Google consent screen."""
    params = (
        f"client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={settings.GOOGLE_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=openid%20email%20profile"
        f"&access_type=offline"
        f"&prompt=select_account"
    )
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{params}")


@router.get("/google/callback")
async def google_callback(
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
) -> Response:
    """Exchange code for tokens, validate email, set cookie."""
    if error or not code:
        raise HTTPException(status_code=400, detail=error or "Missing code")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        tokens = token_resp.json()

        user_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        user_resp.raise_for_status()
        user = user_resp.json()

    email: str = (user.get("email") or "").lower()

    if not email or email not in settings.allowed_emails_set:
        raise HTTPException(status_code=403, detail="Access denied: not on the invite list")

    token = _make_jwt(email, user.get("name", ""), user.get("picture", ""))

    frontend_url = settings.GOOGLE_REDIRECT_URI.split("/api/")[0]
    response = RedirectResponse(url=f"{frontend_url}/app")
    response.set_cookie(
        key="devbuddy_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    return response


@router.get("/me")
async def me(token: Optional[str] = Query(None)) -> dict:
    """Validate JWT and return user info. Accepts token as query param or cookie."""
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return {"email": payload["email"], "name": payload.get("name"), "picture": payload.get("picture")}
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@router.get("/logout")
async def logout() -> Response:
    response = RedirectResponse(url="/")
    response.delete_cookie("devbuddy_token", path="/")
    return response
