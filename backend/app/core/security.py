"""Security utilities - JWT authentication and user extraction."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from app.core.config import settings
from app.models.user import User

# HTTP Bearer token scheme
security_scheme = HTTPBearer(auto_error=False)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> Optional[dict]:
    """Decode and verify JWT token."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        return None


async def get_current_user(
    token: Optional[str] = Query(None, description="JWT token from query param"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> "User":
    """Extract and validate current user from JWT token.

    Token can be provided via:
    1. Query parameter: ?token=<jwt>
    2. Authorization header: Bearer <jwt>
    """
    from app.db.session import async_session_factory
    from app.models.user import User
    from sqlalchemy import select

    # Get token from either source
    jwt_token = token or (credentials.credentials if credentials else None)

    if not jwt_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Provide token via query param or Authorization header.",
        )

    # Decode token
    payload = decode_token(jwt_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # Extract user info from token
    email = payload.get("email") or payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user identification",
        )

    # Find or create user
    async with async_session_factory() as db:
        stmt = select(User).where(User.email == email.lower())
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            # Only auto-create users who are on the invite allowlist.
            if email.lower() not in settings.allowed_emails_set:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Email not in allowed list",
                )

            from app.models.user import Organization

            # Get or create default org
            org_stmt = select(Organization).where(Organization.slug == "default")
            org_result = await db.execute(org_stmt)
            org = org_result.scalar_one_or_none()

            if not org:
                org = Organization(
                    name="Default Organization",
                    slug="default",
                    plan="free",
                )
                db.add(org)
                await db.flush()

            user = User(
                email=email.lower(),
                name=payload.get("name", ""),
                avatar_url=payload.get("picture", ""),
                org_id=org.id,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

        # Update last login
        user.last_login_at = datetime.now(timezone.utc)
        await db.commit()

        return user


async def get_current_user_optional(
    token: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> Optional["User"]:
    """Optional user extraction - returns None if not authenticated."""
    try:
        return await get_current_user(token, credentials)
    except HTTPException:
        return None
