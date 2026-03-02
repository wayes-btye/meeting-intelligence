"""FastAPI dependency for Supabase JWT authentication."""

from __future__ import annotations

import jwt
from fastapi import Header, HTTPException

from src.config import settings


async def get_current_user_id(authorization: str = Header(...)) -> str:
    """Validate Supabase JWT and return the user UUID (sub claim).

    Reads the ``Authorization: Bearer <token>`` header, decodes the Supabase
    JWT using ``SUPABASE_JWT_SECRET``, and returns the user's UUID string.

    Raises:
        HTTPException(401): Missing, malformed, or expired token.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.removeprefix("Bearer ")
    # Fail closed: an empty secret would let PyJWT accept forged HS256 tokens. (#71)
    if not settings.supabase_jwt_secret:
        raise HTTPException(status_code=503, detail="Auth service not configured")
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return str(payload["sub"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
