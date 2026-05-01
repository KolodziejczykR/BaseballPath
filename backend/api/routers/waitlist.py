"""
Waitlist API Router for BaseballPath
Supports the current waitlist flow: simple join + health check.
"""

import logging
from typing import Optional

import sentry_sdk
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr

from ..clients.supabase import require_supabase_admin_client
from ..rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()


class SimpleWaitlistEntry(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    high_school_year: Optional[str] = None


class WaitlistResponse(BaseModel):
    success: bool
    message: str
    id: Optional[str] = None


@router.post("/join", response_model=WaitlistResponse)
# Rate limit: a real user signs up once. The limit is generous enough that
# a confused user submitting twice from a slow form won't hit it, tight
# enough that scripted spam can't drain inserts. Keyed by client IP.
@limiter.limit("10/minute")
async def join_waitlist(
    request: Request,  # noqa: ARG001 — required by SlowAPI for IP keying
    entry: SimpleWaitlistEntry,
) -> WaitlistResponse:
    """
    Waitlist join endpoint.

    Current schema target:
    - email
    - full_name
    - high_school_year

    Fallbacks are preserved for older environments with `name` and/or
    `raffle_entries` columns.
    """
    try:
        supabase = require_supabase_admin_client()
        check_response = (
            supabase.table("waitlist")
            .select("email")
            .eq("email", str(entry.email))
            .execute()
        )

        if check_response.data:
            raise HTTPException(
                status_code=409,
                detail="This email is already on our waitlist!",
            )

        base_entry_data = {"email": str(entry.email)}
        clean_name = (entry.name or "").strip()
        clean_high_school_year = (entry.high_school_year or "").strip()

        # Prefer the new schema first, then gracefully fallback for legacy schemas.
        year_candidates = [base_entry_data]
        if clean_high_school_year:
            year_candidates = [
                {**base_entry_data, "high_school_year": clean_high_school_year},
                base_entry_data,
            ]

        entry_candidates = []
        for year_candidate in year_candidates:
            if clean_name:
                entry_candidates.extend(
                    [
                        {**year_candidate, "full_name": clean_name},
                        {**year_candidate, "name": clean_name},
                    ]
                )
            entry_candidates.extend(
                [
                    year_candidate,
                    {**year_candidate, "raffle_entries": 1},
                ]
            )

        # De-duplicate while preserving order.
        unique_candidates = []
        seen = set()
        for candidate in entry_candidates:
            key = tuple(sorted(candidate.items()))
            if key not in seen:
                seen.add(key)
                unique_candidates.append(candidate)

        insert_response = None
        last_error = None
        for candidate in unique_candidates:
            try:
                insert_response = supabase.table("waitlist").insert([candidate]).execute()
                break
            except Exception as insert_err:  # noqa: BLE001
                error_text = str(insert_err)
                last_error = insert_err
                if (
                    "Could not find the 'name' column" in error_text
                    or "Could not find the 'full_name' column" in error_text
                    or "Could not find the 'high_school_year' column" in error_text
                    or "Could not find the 'raffle_entries' column" in error_text
                ):
                    continue
                raise

        if not insert_response or not insert_response.data:
            if last_error:
                raise last_error
            raise HTTPException(status_code=500, detail="Failed to save waitlist entry")

        entry_id = insert_response.data[0].get("id")

        return WaitlistResponse(
            success=True,
            message="Successfully joined the waitlist!",
            id=entry_id,
        )

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        # Log with traceback for ops visibility, ship to Sentry, and return
        # a generic 500 to the user. The previous "Database error: <raw>"
        # leaked stack-trace-flavored text and was indistinguishable from
        # legitimate constraint violations.
        logger.exception(
            "Waitlist join failed for email=%s",
            entry.email if entry else "(unknown)",
        )
        if sentry_sdk.is_initialized():
            sentry_sdk.capture_exception(exc)
        raise HTTPException(
            status_code=500,
            detail="Failed to join waitlist. Please try again in a moment.",
        ) from exc


@router.get("/health")
async def waitlist_health_check():
    """Health check for waitlist router."""
    return {"status": "ok", "service": "waitlist"}
