from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from jose import jwt
from app.core.security import get_current_user
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    return {
        "id": user["id"],
        "email": user["email"],
    }


class DevTokenRequest(BaseModel):
    email: str = "dev@devbuddy.local"
    name: str = "Dev User"


@router.post("/dev-token", include_in_schema=True)
async def get_dev_token(body: DevTokenRequest):
    if settings.ENVIRONMENT != "development":
        raise HTTPException(status_code=403, detail="Only available in development")

    import uuid
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(uuid.uuid4()),
        "email": body.email,
        "name": body.name,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=24)).timestamp()),
        "role": "authenticated",
    }
    token = jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 86400,
        "user": {"email": body.email, "name": body.name},
    }
