"""
Authenticated account/profile endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..deps.auth import AuthenticatedUser, get_current_user
from ..services.plan_service import (
    get_effective_plan,
    get_monthly_usage,
    get_profile,
    remaining_evaluations,
    update_profile,
)

router = APIRouter()


class ProfilePatchRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=200)
    state: Optional[str] = Field(default=None, min_length=2, max_length=2)
    grad_year: Optional[int] = Field(default=None, ge=2000, le=2100)
    primary_position: Optional[str] = Field(default=None, max_length=10)


def _build_account_response(profile: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    effective_plan = get_effective_plan(user_id)
    usage = get_monthly_usage(user_id)
    return {
        "profile": profile,
        "plan": {
            "tier": effective_plan.plan_tier,
            "status": effective_plan.status,
            "monthly_eval_limit": effective_plan.monthly_eval_limit,
            "llm_enabled": effective_plan.llm_enabled,
            "remaining_evals": remaining_evaluations(effective_plan, usage),
        },
        "usage": {
            "period_start": usage.period_start.isoformat(),
            "eval_count": usage.eval_count,
            "llm_count": usage.llm_count,
        },
    }


@router.get("/me")
async def get_me(current_user: AuthenticatedUser = Depends(get_current_user)) -> Dict[str, Any]:
    profile = get_profile(current_user.user_id, current_user.email)
    return _build_account_response(profile, current_user.user_id)


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
    return _build_account_response(profile, current_user.user_id)
