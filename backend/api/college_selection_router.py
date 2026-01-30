"""
College Selection Router for BaseballPATH
API endpoints for the complete college selection pipeline
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
import json
from datetime import datetime

# Import the pipeline and required types
import os
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.llm.college_selection_pipeline import CollegeSelectionPipeline
from backend.utils.player_types import PlayerInfielder, PlayerOutfielder, PlayerCatcher
from backend.utils.prediction_types import MLPipelineResults, D1PredictionResult, P4PredictionResult
from backend.utils.preferences_types import UserPreferences

router = APIRouter()

@router.post("/analyze")
async def run_college_selection(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the complete college selection pipeline
    
    Expected request format:
    {
        "player_data": {
            "position": "infielder|outfielder|catcher",
            "height": 72,
            "weight": 180,
            "primary_position": "SS",
            "hitting_handedness": "R|L",
            "throwing_hand": "R|L", 
            "region": "Southeast",
            "exit_velo_max": 95.0,
            "sixty_time": 6.8,
            "inf_velo": 85.0,  // for infielders
            "of_velo": 88.0,   // for outfielders  
            "c_velo": 80.0,    // for catchers
            "pop_time": 1.9    // for catchers
        },
        "ml_results": {
            "d1_results": {
                "d1_probability": 0.65,
                "d1_prediction": true,
                "confidence": "High",
                "model_version": "inf_d1_v1.0"
            },
            "p4_results": {
                "p4_probability": 0.25,
                "p4_prediction": false,
                "confidence": "Medium",
                "is_elite": false,
                "model_version": "inf_p4_v1.0",
                "elite_indicators": ["High Exit Velocity"]
            }
        },
        "user_preferences": {
            "preferred_regions": ["Southeast"],
            "max_distance_from_home": 500,
            "min_academic_rating": "B+",
            "preferred_school_size": "Medium",
            "max_tuition_budget": 40000,
            "min_athletics_rating": "B",
            "campus_life_important": true,
            "party_scene_preference": "Moderate",
            "graduation_year": "2026"
        }
    }
    
    Returns:
        Complete college selection analysis with 25 schools
    """
    try:
        # Validate and extract request data
        player_data = request.get("player_data", {})
        ml_data = request.get("ml_results", {})
        preferences_data = request.get("user_preferences", {})
        
        if not player_data:
            raise HTTPException(status_code=400, detail="player_data is required")
        if not ml_data:
            raise HTTPException(status_code=400, detail="ml_results is required")
        
        # Create player object based on position
        player = _create_player_from_data(player_data)
        if not player:
            raise HTTPException(status_code=400, detail="Invalid player data or position")
        
        # Create ML results object
        ml_results = _create_ml_results(player, ml_data)
        if not ml_results:
            raise HTTPException(status_code=400, detail="Invalid ML results data")
        
        # Create user preferences object
        user_preferences = _create_user_preferences(preferences_data)
    
        # Initialize and run pipeline
        pipeline = CollegeSelectionPipeline(delay=1.5)
        
        result = pipeline.run_complete_pipeline(
            player=player,
            ml_results=ml_results,
            user_preferences=user_preferences,
        )
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to generate college recommendations")
        
        return {
            "success": True,
            "message": "College selection analysis completed successfully",
            "analysis": result,
            "metadata": {
                "processed_at": datetime.now().isoformat(),
                "player_position": player.get_player_type(),
                "ml_prediction": ml_results.get_final_prediction(),
                "pipeline_version": "v0.1"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

def _create_player_from_data(player_data: Dict[str, Any]):
    """Create appropriate player object from request data"""
    try:
        position = player_data.get("position", "").lower()
        
        # Common fields for all positions
        common_fields = {
            "height": player_data.get("height"),
            "weight": player_data.get("weight"),
            "primary_position": player_data.get("primary_position"),
            "hitting_handedness": player_data.get("hitting_handedness"),
            "throwing_hand": player_data.get("throwing_hand"),
            "region": player_data.get("region"),
            "exit_velo_max": player_data.get("exit_velo_max"),
            "sixty_time": player_data.get("sixty_time")
        }
        
        # Validate required fields
        required_fields = ["height", "weight", "primary_position", "hitting_handedness", "throwing_hand", "region"]
        for field in required_fields:
            if common_fields[field] is None:
                return None
        
        if position == "infielder":
            inf_velo = player_data.get("inf_velo")
            if inf_velo is None:
                return None
            return PlayerInfielder(inf_velo=inf_velo, **common_fields)
            
        elif position == "outfielder":
            of_velo = player_data.get("of_velo")
            if of_velo is None:
                return None
            return PlayerOutfielder(of_velo=of_velo, **common_fields)
            
        elif position == "catcher":
            c_velo = player_data.get("c_velo")
            pop_time = player_data.get("pop_time")
            if c_velo is None or pop_time is None:
                return None
            return PlayerCatcher(c_velo=c_velo, pop_time=pop_time, **common_fields)
            
        return None
        
    except Exception:
        return None

def _create_ml_results(player, ml_data: Dict[str, Any]):
    """Create MLPipelineResults object from request data"""
    try:
        d1_data = ml_data.get("d1_results", {})
        p4_data = ml_data.get("p4_results")
        
        # Create D1 results
        d1_results = D1PredictionResult(
            d1_probability=d1_data.get("d1_probability", 0.0),
            d1_prediction=d1_data.get("d1_prediction", False),
            confidence=d1_data.get("confidence", "Medium"),
            model_version=d1_data.get("model_version", "unknown")
        )
        
        # Create P4 results if provided
        p4_results = None
        if p4_data:
            p4_results = P4PredictionResult(
                p4_probability=p4_data.get("p4_probability", 0.0),
                p4_prediction=p4_data.get("p4_prediction", False),
                confidence=p4_data.get("confidence", "Medium"),
                is_elite=p4_data.get("is_elite", False),
                model_version=p4_data.get("model_version", "unknown"),
                elite_indicators=p4_data.get("elite_indicators", [])
            )
        
        return MLPipelineResults(
            player=player,
            d1_results=d1_results,
            p4_results=p4_results
        )
        
    except Exception:
        return None

def _create_user_preferences(preferences_data: Dict[str, Any]) -> UserPreferences:
    """Create UserPreferences object from request data"""
    return UserPreferences(
        user_state=preferences_data.get("user_state", "CA"),
        preferred_regions=preferences_data.get("preferred_regions"),
        min_academic_rating=preferences_data.get("min_academic_rating"),
        preferred_school_size=preferences_data.get("preferred_school_size"),
        max_budget=preferences_data.get("max_tuition_budget"),
        min_athletics_rating=preferences_data.get("min_athletics_rating"),
        party_scene_preference=preferences_data.get("party_scene_preference"),
        hs_graduation_year=preferences_data.get("graduation_year")
    )

@router.get("/example")
async def get_selection_example() -> Dict[str, Any]:
    """
    Get an example request for the college selection endpoint
    
    Returns:
        Example request structure with sample data
    """
    example_request = {
        "player_data": {
            "position": "infielder",
            "height": 72,
            "weight": 180,
            "primary_position": "SS",
            "hitting_handedness": "R",
            "throwing_hand": "R",
            "region": "Southeast",
            "exit_velo_max": 95.0,
            "sixty_time": 6.8,
            "inf_velo": 85.0
        },
        "ml_results": {
            "d1_results": {
                "d1_probability": 0.65,
                "d1_prediction": True,
                "confidence": "High",
                "model_version": "inf_d1_v1.0"
            },
            "p4_results": {
                "p4_probability": 0.25,
                "p4_prediction": False,
                "confidence": "Medium",
                "is_elite": False,
                "model_version": "inf_p4_v1.0",
                "elite_indicators": ["High Exit Velocity"]
            }
        },
        "user_preferences": {
            "user_state": "NC",
            "preferred_regions": ["Southeast", "South"],
            "min_academic_rating": "B+",
            "preferred_school_size": ["Medium", "Large"],
            "max_tuition_budget": 40000,
            "min_athletics_rating": "B",
            "party_scene_preference": ["Moderate"],
            "graduation_year": "2026"
        }
    }
    
    return {
        "description": "Submit college selection request using POST /college-selection/analyze",
        "example_request": example_request,
        "notes": [
            "Position-specific fields: inf_velo (infielders), of_velo (outfielders), c_velo + pop_time (catchers)",
            "ML results support both D1 and P4 predictions",
            "User preferences are all optional but help with ranking",
            "Pipeline typically takes 2-3 minutes to complete due to data scraping"
        ]
    }

@router.get("/health")
async def selection_health_check() -> Dict[str, str]:
    """Health check for college selection router"""
    return {"status": "ok", "service": "college_selection"}