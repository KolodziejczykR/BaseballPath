"""
User feedback endpoints — per-school thumbs and per-run survey.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..clients.supabase import require_supabase_admin_client
from ..deps.auth import AuthenticatedUser, get_current_user

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SchoolFeedbackRequest(BaseModel):
    evaluation_run_id: str = Field(min_length=1, max_length=80)
    school_dedupe_key: str = Field(min_length=1, max_length=400)
    school_name: str = Field(min_length=1, max_length=300)
    is_good_fit: bool
    reason: Optional[str] = Field(default=None, max_length=500)


class RunFeedbackRequest(BaseModel):
    evaluation_run_id: str = Field(min_length=1, max_length=80)
    level_rating: Optional[str] = Field(default=None)
    match_quality: Optional[int] = Field(default=None, ge=1, le=5)
    discovery: Optional[str] = Field(default=None)
    improvement: Optional[str] = Field(default=None, max_length=2000)
    praise: Optional[str] = Field(default=None, max_length=2000)
    quote_consent: bool = False
    display_name: Optional[str] = Field(default=None, max_length=200)


class RunFeedbackDismissRequest(BaseModel):
    evaluation_run_id: str = Field(min_length=1, max_length=80)


_LEVEL_RATINGS = {"too_low", "just_right", "too_high"}
_DISCOVERY_VALUES = {"yes", "some", "no"}


def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _verify_run_ownership(run_id: str, user_id: str) -> None:
    supabase = require_supabase_admin_client()
    response = (
        supabase.table("prediction_runs")
        .select("id")
        .eq("id", run_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation run not found",
        )


# ---------------------------------------------------------------------------
# Per-school thumbs
# ---------------------------------------------------------------------------


@router.post("/school")
async def upsert_school_feedback(
    payload: SchoolFeedbackRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    _verify_run_ownership(payload.evaluation_run_id, current_user.user_id)

    supabase = require_supabase_admin_client()
    record = {
        "user_id": current_user.user_id,
        "evaluation_run_id": payload.evaluation_run_id,
        "school_dedupe_key": payload.school_dedupe_key,
        "school_name": payload.school_name.strip(),
        "is_good_fit": payload.is_good_fit,
        "reason": _normalize_optional_text(payload.reason),
    }

    response = (
        supabase.table("school_feedback")
        .upsert(record, on_conflict="user_id,evaluation_run_id,school_dedupe_key")
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save school feedback",
        )
    return response.data[0]


@router.get("/school")
async def list_school_feedback(
    evaluation_run_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    _verify_run_ownership(evaluation_run_id, current_user.user_id)

    supabase = require_supabase_admin_client()
    response = (
        supabase.table("school_feedback")
        .select("*")
        .eq("user_id", current_user.user_id)
        .eq("evaluation_run_id", evaluation_run_id)
        .execute()
    )
    items: List[Dict[str, Any]] = response.data or []
    return {"items": items, "count": len(items)}


# ---------------------------------------------------------------------------
# Per-run survey feedback
# ---------------------------------------------------------------------------


@router.get("/run/eligibility")
async def run_feedback_eligibility(
    evaluation_run_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Returns whether this run should prompt the survey modal.

    Eligible if:
      - The run belongs to the user.
      - It is the user's earliest run (their first evaluation).
      - No prior submission/dismissal exists for this run.
    """
    _verify_run_ownership(evaluation_run_id, current_user.user_id)

    supabase = require_supabase_admin_client()

    earliest = (
        supabase.table("prediction_runs")
        .select("id, created_at")
        .eq("user_id", current_user.user_id)
        .order("created_at", desc=False)
        .limit(1)
        .execute()
    )
    is_first_run = bool(earliest.data) and earliest.data[0].get("id") == evaluation_run_id

    existing = (
        supabase.table("evaluation_feedback")
        .select("id, dismissed, match_quality")
        .eq("user_id", current_user.user_id)
        .eq("evaluation_run_id", evaluation_run_id)
        .limit(1)
        .execute()
    )
    has_record = bool(existing.data)

    eligible = is_first_run and not has_record
    return {
        "eligible": eligible,
        "is_first_run": is_first_run,
        "has_record": has_record,
    }


@router.post("/run")
async def submit_run_feedback(
    payload: RunFeedbackRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    _verify_run_ownership(payload.evaluation_run_id, current_user.user_id)

    if payload.level_rating is not None and payload.level_rating not in _LEVEL_RATINGS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid level_rating",
        )
    if payload.discovery is not None and payload.discovery not in _DISCOVERY_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid discovery value",
        )

    display_name = _normalize_optional_text(payload.display_name)
    if payload.quote_consent and not display_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="display_name is required when quote_consent is true",
        )

    record = {
        "user_id": current_user.user_id,
        "evaluation_run_id": payload.evaluation_run_id,
        "level_rating": payload.level_rating,
        "match_quality": payload.match_quality,
        "discovery": payload.discovery,
        "improvement": _normalize_optional_text(payload.improvement),
        "praise": _normalize_optional_text(payload.praise),
        "quote_consent": payload.quote_consent,
        "display_name": display_name,
        "dismissed": False,
    }

    supabase = require_supabase_admin_client()
    response = (
        supabase.table("evaluation_feedback")
        .upsert(record, on_conflict="user_id,evaluation_run_id")
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save feedback",
        )
    return response.data[0]


@router.post("/run/dismiss")
async def dismiss_run_feedback(
    payload: RunFeedbackDismissRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    _verify_run_ownership(payload.evaluation_run_id, current_user.user_id)

    record = {
        "user_id": current_user.user_id,
        "evaluation_run_id": payload.evaluation_run_id,
        "dismissed": True,
    }

    supabase = require_supabase_admin_client()
    response = (
        supabase.table("evaluation_feedback")
        .upsert(record, on_conflict="user_id,evaluation_run_id")
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to dismiss feedback",
        )
    return {"dismissed": True}
