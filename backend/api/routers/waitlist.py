"""
Waitlist API Router for BaseballPath
Supports the current waitlist flow: simple join + health check.
"""

import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from supabase import Client, create_client

load_dotenv()

router = APIRouter()

# Initialize Supabase client with service role key
supabase_url = os.getenv("SUPABASE_URL")
supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")

if not supabase_url or not supabase_service_key:
    raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

supabase: Client = create_client(supabase_url, supabase_service_key)


class SimpleWaitlistEntry(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    high_school_year: Optional[str] = None


class WaitlistResponse(BaseModel):
    success: bool
    message: str
    id: Optional[str] = None


@router.post("/join", response_model=WaitlistResponse)
async def join_waitlist(entry: SimpleWaitlistEntry) -> WaitlistResponse:
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
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/health")
async def waitlist_health_check():
    """Health check for waitlist router."""
    return {"status": "ok", "service": "waitlist"}
