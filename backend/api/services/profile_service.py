"""
Profile helpers — ensure/read/update rows in public.profiles.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException, status

from ..clients.supabase import require_supabase_admin_client


def _row_to_dict(row: Any) -> Dict[str, Any]:
    if isinstance(row, dict):
        return row
    return dict(row)


def ensure_profile_exists(user_id: str, email: Optional[str] = None) -> Dict[str, Any]:
    supabase = require_supabase_admin_client()
    existing = (
        supabase.table("profiles")
        .select("*")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        return _row_to_dict(existing.data[0])

    insert_payload: Dict[str, Any] = {"id": user_id}
    if email:
        insert_payload["full_name"] = email.split("@")[0]

    inserted = supabase.table("profiles").insert(insert_payload).execute()
    if not inserted.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create profile row",
        )
    return _row_to_dict(inserted.data[0])


def get_profile(user_id: str, email: Optional[str] = None) -> Dict[str, Any]:
    return ensure_profile_exists(user_id=user_id, email=email)


def update_profile(user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    supabase = require_supabase_admin_client()
    response = (
        supabase.table("profiles")
        .update(updates)
        .eq("id", user_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile update failed",
        )
    return _row_to_dict(response.data[0])
