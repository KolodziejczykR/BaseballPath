from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from backend.utils.preferences_types import UserPreferences, PreferencesRequest, PreferencesResponse

router = APIRouter()

@router.post("/submit")
async def submit_preferences(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Submit user preferences for college selection
    
    Args:
        request: Dictionary containing user preferences and player position
    
    Returns:
        Confirmation response with received preferences
    """
    try:
        # Parse the request
        preferences_data = request.get("preferences", {})
        player_position = request.get("player_position", "")
        
        # Create UserPreferences object
        user_preferences = UserPreferences(
            preferred_regions=preferences_data.get("preferred_regions"),
            max_distance_from_home=preferences_data.get("max_distance_from_home"),
            min_academic_rating=preferences_data.get("min_academic_rating"),
            preferred_school_size=preferences_data.get("preferred_school_size"),
            max_tuition_budget=preferences_data.get("max_tuition_budget"),
            financial_aid_important=preferences_data.get("financial_aid_important", False),
            min_athletics_rating=preferences_data.get("min_athletics_rating"),
            playing_time_priority=preferences_data.get("playing_time_priority", "Medium"),
            campus_life_important=preferences_data.get("campus_life_important", False),
            party_scene_preference=preferences_data.get("party_scene_preference")
        )
        
        # Create response
        response = PreferencesResponse(
            message="Preferences received successfully",
            preferences_received=user_preferences
        )
        
        return response.to_dict()
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing preferences: {str(e)}")

@router.get("/example")
async def get_preferences_example() -> Dict[str, Any]:
    """
    Get an example of the preferences request format
    
    Returns:
        Example preferences request structure
    """
    example_preferences = UserPreferences(
        preferred_regions=["Southeast", "Mid-Atlantic"],
        max_distance_from_home=500,
        min_academic_rating="B+",
        preferred_school_size="Medium",
        max_tuition_budget=35000,
        financial_aid_important=True,
        min_athletics_rating="B",
        playing_time_priority="High",
        campus_life_important=True,
        party_scene_preference="Moderate"
    )
    
    example_request = PreferencesRequest(
        preferences=example_preferences,
        player_position="infielder"
    )
    
    return {
        "example_request": example_request.to_dict(),
        "description": "Submit preferences using POST /preferences/submit with this structure"
    }

@router.get("/health")
async def preferences_health_check() -> Dict[str, str]:
    """Health check for preferences router"""
    return {"status": "ok", "service": "preferences"}