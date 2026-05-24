import base64
import logging

import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.errors import error_payload
from app.models import User

logger = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)

# PyJWKClient caches keys internally — one instance for the process lifetime
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        pk = settings.clerk_publishable_key
        # Publishable key format: pk_test_<base64(frontend-api-host + "$")>
        b64 = pk.split("_", 2)[2]
        padding = (4 - len(b64) % 4) % 4
        frontend_api = base64.b64decode(b64 + "=" * padding).decode().rstrip("$")
        jwks_url = f"https://{frontend_api}/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


def _verify_jwt(token: str) -> dict:
    client = _get_jwks_client()
    signing_key = client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        options={"verify_aud": False},  # Clerk doesn't populate aud
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_payload("UNAUTHORIZED", "Missing bearer token"),
        )

    try:
        payload = _verify_jwt(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_payload("TOKEN_EXPIRED", "Token has expired"),
        )
    except jwt.InvalidTokenError as e:
        logger.warning("JWT verification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_payload("INVALID_TOKEN", "Token verification failed"),
        )
    except Exception as e:
        logger.error("Token verification error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_payload("AUTH_UNAVAILABLE", "Auth service unavailable"),
        )

    clerk_user_id = payload.get("sub")
    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_payload("INVALID_TOKEN", "No user ID in token"),
        )

    # Upsert user — handles race condition where webhook hasn't fired yet
    result = await db.execute(select(User).where(User.clerk_user_id == clerk_user_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            clerk_user_id=clerk_user_id,
            email=payload.get("email", ""),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user


async def get_current_user_from_query(
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Used by SSE endpoint which can't set Authorization header via EventSource."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_payload("UNAUTHORIZED", "Missing token"),
        )
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    return await get_current_user(credentials=creds, db=db)
