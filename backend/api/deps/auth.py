"""
Authentication dependency for protected API endpoints.

Uses Supabase Auth to validate bearer tokens, then enforces issuer/audience checks.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..clients.supabase import (
    get_supabase_url,
    require_supabase_admin_client,
)

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthenticatedUser:
    user_id: str
    email: Optional[str]
    access_token: str
    claims: Dict[str, Any]


def _decode_jwt_payload(token: str) -> Dict[str, Any]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT structure")
        payload = parts[1]
        padding = "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload + padding)
        parsed = json.loads(decoded.decode("utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError("JWT payload is not an object")
        return parsed
    except Exception as exc:  # pragma: no cover - defensive parsing branch
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token payload: {str(exc)}",
        ) from exc


def _validate_issuer_and_audience(claims: Dict[str, Any]) -> None:
    supabase_url = get_supabase_url()
    expected_iss = os.getenv("SUPABASE_JWT_ISSUER")
    if not expected_iss and supabase_url:
        expected_iss = f"{supabase_url.rstrip('/')}/auth/v1"

    if expected_iss:
        token_iss = claims.get("iss")
        if token_iss != expected_iss:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token issuer",
            )

    expected_aud = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")
    token_aud = claims.get("aud")
    if isinstance(token_aud, list):
        valid = expected_aud in token_aud
    else:
        valid = token_aud == expected_aud
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token audience",
        )


def _resolve_auth_user_obj(get_user_response: Any) -> Any:
    # supabase-py typically returns an object with .user
    if hasattr(get_user_response, "user"):
        return getattr(get_user_response, "user")
    # Defensive fallback if response shape differs
    if isinstance(get_user_response, dict):  # pragma: no cover
        return get_user_response.get("user")
    return None


def _get_attr_or_key(obj: Any, key: str) -> Any:
    if obj is None:
        return None
    if hasattr(obj, key):
        return getattr(obj, key)
    if isinstance(obj, dict):  # pragma: no cover
        return obj.get(key)
    return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    access_token = credentials.credentials
    claims = _decode_jwt_payload(access_token)
    _validate_issuer_and_audience(claims)

    supabase = require_supabase_admin_client()
    try:
        user_response = supabase.auth.get_user(access_token)
        auth_user = _resolve_auth_user_obj(user_response)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {str(exc)}",
        ) from exc

    if auth_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is not associated with an authenticated user",
        )

    user_id = _get_attr_or_key(auth_user, "id")
    email = _get_attr_or_key(auth_user, "email")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user id was not found in token response",
        )

    return AuthenticatedUser(
        user_id=str(user_id),
        email=str(email) if email else None,
        access_token=access_token,
        claims=claims,
    )
