"""
Authenticated account/profile endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..deps.auth import AuthenticatedUser, get_current_user
from ..services.profile_service import get_profile, update_profile

router = APIRouter()


class ProfilePatchRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=200)
    state: Optional[str] = Field(default=None, min_length=2, max_length=2)
    grad_year: Optional[int] = Field(default=None, ge=2000, le=2100)
    primary_position: Optional[str] = Field(default=None, max_length=10)


def _build_account_response(profile: Dict[str, Any]) -> Dict[str, Any]:
    return {"profile": profile}


@router.get("/me")
async def get_me(current_user: AuthenticatedUser = Depends(get_current_user)) -> Dict[str, Any]:
    profile = get_profile(current_user.user_id, current_user.email)
    return _build_account_response(profile)


@router.patch("/me")
async def patch_me(
    payload: ProfilePatchRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if updates:
        if "state" in updates and isinstance(updates["state"], str):
            updates["state"] = updates["state"].upper()
        if "primary_position" in updates and isinstance(updates["primary_position"], str):
            updates["primary_position"] = updates["primary_position"].upper()
        profile = update_profile(current_user.user_id, updates)
    else:
        profile = get_profile(current_user.user_id, current_user.email)
    return _build_account_response(profile)
