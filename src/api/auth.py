"""FastAPI dependency for Supabase JWT authentication."""

from __future__ import annotations

import jwt
from fastapi import Header, HTTPException
from jwt import PyJWKClient

from src.config import settings

# Module-level JWKS client — fetches Supabase's public signing keys once and
# caches them. Handles key rotation automatically: if Supabase rotates to a
# new signing key the client re-fetches on the next cache miss. (#71)
# Supabase has migrated this project from HS256 to ES256 (ECDSA P-256) so we
# use the JWKS endpoint rather than a static secret.
_JWKS_URL = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
_jwks_client = PyJWKClient(_JWKS_URL, cache_keys=True)


async def get_current_user_id(authorization: str = Header(...)) -> str:
    """Validate Supabase JWT and return the user UUID (sub claim).

    Reads the ``Authorization: Bearer <token>`` header, fetches the matching
    signing key from Supabase's JWKS endpoint, and verifies the token.
    Works with any algorithm Supabase uses (currently ES256).

    Raises:
        HTTPException(401): Missing, malformed, or expired token.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.removeprefix("Bearer ")
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
        )
        return str(payload["sub"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
