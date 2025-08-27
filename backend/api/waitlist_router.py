"""
Waitlist API Router for BaseballPATH
Handles secure waitlist operations using service role key
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

# Initialize Supabase client with service role key
supabase_url = os.getenv("SUPABASE_URL")
supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")

if not supabase_url or not supabase_service_key:
    raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

supabase: Client = create_client(supabase_url, supabase_service_key)

# Pydantic models
class EmailCheckRequest(BaseModel):
    email: EmailStr

class EmailCheckResponse(BaseModel):
    exists: bool

class WaitlistEntry(BaseModel):
    email: EmailStr
    budget: Optional[str] = None
    travel_team: Optional[str] = None
    recruiting_agency: Optional[str] = None
    graduation_year: Optional[str] = None
    recruiting_challenge: Optional[str] = None
    desired_features: Optional[str] = None
    additional_info: Optional[str] = None

class WaitlistResponse(BaseModel):
    success: bool
    message: str
    id: Optional[str] = None

@router.post("/check-email", response_model=EmailCheckResponse)
async def check_email(request: EmailCheckRequest) -> EmailCheckResponse:
    """
    Check if an email already exists in the waitlist
    
    Args:
        request: Email to check
        
    Returns:
        EmailCheckResponse with exists boolean
    """
    try:
        response = supabase.table("waitlist")\
            .select("email")\
            .eq("email", str(request.email))\
            .execute()
        
        exists = len(response.data) > 0
        return EmailCheckResponse(exists=exists)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/submit", response_model=WaitlistResponse)
async def submit_waitlist_entry(entry: WaitlistEntry) -> WaitlistResponse:
    """
    Submit a complete waitlist entry with survey data
    
    Args:
        entry: Complete waitlist entry data
        
    Returns:
        WaitlistResponse with success status and ID
    """
    try:
        # Check if email already exists
        check_response = supabase.table("waitlist")\
            .select("email")\
            .eq("email", str(entry.email))\
            .execute()
        
        if check_response.data:
            raise HTTPException(
                status_code=409, 
                detail="This email is already on our waitlist!"
            )
        
        # Insert new waitlist entry
        insert_response = supabase.table("waitlist")\
            .insert([entry.dict()])\
            .execute()
        
        if not insert_response.data:
            raise HTTPException(
                status_code=500, 
                detail="Failed to save waitlist entry"
            )
        
        entry_id = insert_response.data[0].get('id')
        
        return WaitlistResponse(
            success=True,
            message="Successfully joined the waitlist!",
            id=entry_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/health")
async def waitlist_health_check():
    """Health check for waitlist router"""
    return {"status": "ok", "service": "waitlist"}