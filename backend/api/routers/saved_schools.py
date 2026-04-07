"""
Authenticated saved schools endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..clients.supabase import require_supabase_admin_client
from ..deps.auth import AuthenticatedUser, get_current_user

router = APIRouter()


class SavedSchoolCreateRequest(BaseModel):
    school_name: str = Field(min_length=1, max_length=300)
    school_logo_image: Optional[str] = Field(default=None, max_length=300)
    school_data: Dict[str, Any] = Field(default_factory=dict)
    note: Optional[str] = Field(default=None, max_length=2000)
    evaluation_run_id: Optional[str] = Field(default=None, max_length=80)


class SavedSchoolNotePatchRequest(BaseModel):
    note: Optional[str] = Field(default="", max_length=2000)


def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _build_dedupe_key(school_name: str, school_logo_image: Optional[str]) -> str:
    logo_key = _normalize_optional_text(school_logo_image)
    if logo_key:
        return f"logo:{logo_key.lower()}"
    return f"name:{school_name.strip().lower()}"


def _get_saved_school(saved_school_id: str, user_id: str) -> Dict[str, Any]:
    supabase = require_supabase_admin_client()
    response = (
        supabase.table("saved_schools")
        .select("*")
        .eq("id", saved_school_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved school not found")
    return response.data[0]


@router.get("")
async def list_saved_schools(current_user: AuthenticatedUser = Depends(get_current_user)) -> Dict[str, Any]:
    supabase = require_supabase_admin_client()
    response = (
        supabase.table("saved_schools")
        .select("*")
        .eq("user_id", current_user.user_id)
        .order("created_at", desc=True)
        .execute()
    )
    items = response.data or []
    return {"items": items, "count": len(items)}


@router.post("")
async def create_saved_school(
    payload: SavedSchoolCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    school_name = payload.school_name.strip()
    if not school_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="school_name is required")

    school_logo_image = _normalize_optional_text(payload.school_logo_image)
    dedupe_key = _build_dedupe_key(school_name, school_logo_image)

    supabase = require_supabase_admin_client()

    if payload.evaluation_run_id:
        run_check = (
            supabase.table("prediction_runs")
            .select("id")
            .eq("id", payload.evaluation_run_id)
            .eq("user_id", current_user.user_id)
            .limit(1)
            .execute()
        )
        if not run_check.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")

    existing = (
        supabase.table("saved_schools")
        .select("*")
        .eq("user_id", current_user.user_id)
        .eq("dedupe_key", dedupe_key)
        .limit(1)
        .execute()
    )
    if existing.data:
        existing_row = existing.data[0]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "school_already_saved",
                "saved_school_id": existing_row.get("id"),
                "school_name": existing_row.get("school_name"),
            },
        )

    insert_payload = {
        "user_id": current_user.user_id,
        "school_name": school_name,
        "school_logo_image": school_logo_image,
        "dedupe_key": dedupe_key,
        "school_data": payload.school_data or {},
        "note": _normalize_optional_text(payload.note),
        "evaluation_run_id": _normalize_optional_text(payload.evaluation_run_id),
    }
    insert_response = supabase.table("saved_schools").insert(insert_payload).execute()
    if not insert_response.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save school")
    return insert_response.data[0]


@router.get("/{saved_school_id}")
async def get_saved_school(
    saved_school_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    return _get_saved_school(saved_school_id, current_user.user_id)


@router.patch("/{saved_school_id}")
async def update_saved_school_note(
    saved_school_id: str,
    payload: SavedSchoolNotePatchRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    _get_saved_school(saved_school_id, current_user.user_id)
    supabase = require_supabase_admin_client()
    response = (
        supabase.table("saved_schools")
        .update({"note": _normalize_optional_text(payload.note)})
        .eq("id", saved_school_id)
        .eq("user_id", current_user.user_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update saved school")
    return response.data[0]


@router.delete("/{saved_school_id}")
async def delete_saved_school(
    saved_school_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    _get_saved_school(saved_school_id, current_user.user_id)
    supabase = require_supabase_admin_client()
    supabase.table("saved_schools").delete().eq("id", saved_school_id).eq("user_id", current_user.user_id).execute()
    return {"deleted": True, "saved_school_id": saved_school_id}
