"""
Waitlist API Router for BaseballPATH
Handles secure waitlist operations using service role key
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional
import os
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
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

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

def generate_verification_token():
    """Generate a 6-digit verification token"""
    return f"{random.randint(100000, 999999)}"

def send_verification_email(email: str, token: str):
    """Send verification email with 6-digit token"""
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        raise HTTPException(status_code=500, detail="Email configuration not set up")
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = email
        msg['Subject'] = "BaseballPATH - Verify Your Email"
        
        # Email body
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="text-align: center; margin-bottom: 30px;">
                <h1 style="color: #6b7ff2; margin-bottom: 10px;">BaseballPATH</h1>
                <h2 style="color: #333; margin-bottom: 20px;">Verify Your Email</h2>
            </div>
            
            <div style="background: #f8f9fa; padding: 25px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
                <p style="font-size: 16px; color: #555; margin-bottom: 15px;">Your verification code is:</p>
                <div style="font-size: 32px; font-weight: bold; color: #6b7ff2; letter-spacing: 5px; margin: 20px 0;">{token}</div>
                <p style="font-size: 14px; color: #777;">This code expires in 10 minutes.</p>
            </div>
            
            <p style="color: #555; font-size: 14px; text-align: center;">
                Thanks for joining the BaseballPATH waitlist!<br>
                Enter this code on the website to continue.
            </p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # Connect to server and send email
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_ADDRESS, email, text)
        server.quit()
        
        return True
    except Exception as e:
        print(f"Email sending failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send verification email: {str(e)}")

# Pydantic models
class EmailCheckRequest(BaseModel):
    email: EmailStr

class EmailCheckResponse(BaseModel):
    exists: bool

class WaitlistEntry(BaseModel):
    email: EmailStr
    user_type: str
    high_school_year: str
    email_consent: bool
    raffle_entries: Optional[int] = 1

class WaitlistResponse(BaseModel):
    success: bool
    message: str
    id: Optional[str] = None

class SurveyData(BaseModel):
    lead_id: str
    user_type: Optional[str] = None
    grad_year: Optional[str] = None
    college_level: str
    priorities: list[str]
    priority_other: Optional[str] = None
    attended_showcases: str
    showcase_count: Optional[str] = None
    showcase_orgs: Optional[list[str]] = None
    recruiting_budget: str
    tool_budget: int
    additional_features: Optional[str] = None

class RaffleUpdateResponse(BaseModel):
    success: bool
    message: str
    new_entries: int

class EmailVerificationRequest(BaseModel):
    email: EmailStr

class EmailVerificationResponse(BaseModel):
    success: bool
    message: str
    
class TokenVerificationRequest(BaseModel):
    email: EmailStr
    token: str
    
class TokenVerificationResponse(BaseModel):
    success: bool
    message: str
    verified: bool

@router.post("/send-verification", response_model=EmailVerificationResponse)
async def send_verification(request: EmailVerificationRequest) -> EmailVerificationResponse:
    """
    Send verification email with 6-digit token
    
    Args:
        request: Email to send verification to
        
    Returns:
        EmailVerificationResponse with success status
    """
    try:
        # Check if email already exists in waitlist
        response = supabase.table("waitlist")\
            .select("email")\
            .eq("email", str(request.email))\
            .execute()
        
        if response.data:
            raise HTTPException(
                status_code=409, 
                detail="This email is already on our waitlist!"
            )
        
        # Generate token
        token = generate_verification_token()
        
        # Store verification token in database (temporary table)
        verification_data = {
            "email": str(request.email),
            "token": token,
            "expires_at": (datetime.utcnow() + timedelta(minutes=10)).isoformat(),
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Create or update verification entry
        supabase.table("email_verifications")\
            .upsert(verification_data, on_conflict="email")\
            .execute()
        
        # Send email
        send_verification_email(str(request.email), token)
        
        return EmailVerificationResponse(
            success=True,
            message="Verification email sent! Check your inbox for the 6-digit code."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/verify-token", response_model=TokenVerificationResponse)
async def verify_token(request: TokenVerificationRequest) -> TokenVerificationResponse:
    """
    Verify the 6-digit token for email verification
    
    Args:
        request: Email and token to verify
        
    Returns:
        TokenVerificationResponse with verification status
    """
    try:
        # Get verification record
        response = supabase.table("email_verifications")\
            .select("*")\
            .eq("email", str(request.email))\
            .execute()
        
        if not response.data:
            return TokenVerificationResponse(
                success=False,
                message="No verification request found for this email.",
                verified=False
            )
        
        verification = response.data[0]
        
        # Check if token matches
        if verification["token"] != request.token:
            return TokenVerificationResponse(
                success=False,
                message="Invalid verification code. Please try again.",
                verified=False
            )
        
        # Check if token is expired
        expires_at = datetime.fromisoformat(verification["expires_at"].replace('Z', '+00:00'))
        if datetime.utcnow().replace(tzinfo=expires_at.tzinfo) > expires_at:
            return TokenVerificationResponse(
                success=False,
                message="Verification code has expired. Please request a new one.",
                verified=False
            )
        
        # Mark as verified and delete verification record
        supabase.table("email_verifications")\
            .delete()\
            .eq("email", str(request.email))\
            .execute()
        
        return TokenVerificationResponse(
            success=True,
            message="Email verified successfully!",
            verified=True
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

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
        
        # Insert new waitlist entry with default raffle_entries = 1
        entry_data = entry.dict()
        if 'raffle_entries' not in entry_data or entry_data['raffle_entries'] is None:
            entry_data['raffle_entries'] = 1
            
        insert_response = supabase.table("waitlist")\
            .insert([entry_data])\
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

@router.post("/complete-survey", response_model=RaffleUpdateResponse)
async def complete_survey(survey_data: SurveyData) -> RaffleUpdateResponse:
    """
    Submit survey completion and update raffle entries to 4 (1 + 3 bonus)
    
    Args:
        survey_data: Complete survey response data
        
    Returns:
        RaffleUpdateResponse with success status and new entry count
    """
    try:
        # Find user by ID
        user_response = supabase.table("waitlist")\
            .select("*")\
            .eq("id", survey_data.lead_id)\
            .execute()
        
        if not user_response.data:
            raise HTTPException(
                status_code=404, 
                detail="User not found in waitlist"
            )
        
        user = user_response.data[0]
        current_entries = user.get('raffle_entries', 1)
        
        # Update raffle entries to 4 (original 1 + 3 bonus)
        new_entries = 4
        
        # Update user record with survey data and new raffle entries
        update_data = {
            'raffle_entries': new_entries,
            'survey_completed': True,
            'survey_data': survey_data.dict()
        }
        
        update_response = supabase.table("waitlist")\
            .update(update_data)\
            .eq("id", survey_data.lead_id)\
            .execute()
        
        if not update_response.data:
            raise HTTPException(
                status_code=500, 
                detail="Failed to update survey completion"
            )
        
        return RaffleUpdateResponse(
            success=True,
            message=f"Survey completed! You now have {new_entries} raffle entries.",
            new_entries=new_entries
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/entries/{user_id}")
async def get_raffle_entries(user_id: str):
    """Get current raffle entries for a user"""
    try:
        response = supabase.table("waitlist")\
            .select("raffle_entries, survey_completed")\
            .eq("id", user_id)\
            .execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = response.data[0]
        return {
            "raffle_entries": user_data.get('raffle_entries', 1),
            "survey_completed": user_data.get('survey_completed', False)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/health")
async def waitlist_health_check():
    """Health check for waitlist router"""
    return {"status": "ok", "service": "waitlist"}