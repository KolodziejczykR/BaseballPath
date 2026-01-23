"""
School Preferences and Filtering Router for BaseballPATH
API endpoints for user preference-based school filtering with two-tier system
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

# Import the filtering pipeline and required types
import os
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.school_filtering.async_two_tier_pipeline import get_school_matches_shared, count_eligible_schools_shared
from backend.utils.preferences_types import UserPreferences
from backend.utils.prediction_types import MLPipelineResults, D1PredictionResult, P4PredictionResult
from backend.utils.player_types import PlayerInfielder, PlayerOutfielder, PlayerCatcher

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/filter")
async def filter_schools_by_preferences(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    🎯 MAIN ENDPOINT: Filter schools based on user preferences and ML predictions

    This endpoint integrates user preferences with ML predictions to return a ranked list
    of schools with detailed PROs/CONs analysis using our two-tier filtering system.

    Expected request format:
    {
        "user_preferences": {
            "user_state": "CA",               # REQUIRED - for in-state tuition calculation
            "preferred_states": ["CA", "TX"], # Multi-select list
            "preferred_regions": ["West"],    # Multi-select list
            "preferred_school_size": ["Medium", "Large"], # Multi-select list
            "max_budget": 35000,              # Annual budget limit
            "min_academic_rating": "B+",      # Minimum academic grade
            "min_athletics_rating": "B",      # Minimum athletics grade
            "min_student_satisfaction_rating": "B+", # Student life rating
            "party_scene_preference": ["Moderate"], # Multi-select list
            "gpa": 3.5,                       # Student's GPA
            "sat": 1350,                      # Student's SAT score
            "act": 30,                        # Student's ACT score
            "intended_major_buckets": "Engineering", # Major area
            "hs_graduation_year": "2025",     # Graduation year
            "must_have_preferences": ["max_budget", "min_academic_rating"] # Dynamic must-haves
        },
        "ml_results": {
            "d1_results": {
                "d1_probability": 0.75,
                "d1_prediction": true,
                "confidence": "High",
                "model_version": "v2.1"
            },
            "p4_results": {
                "p4_probability": 0.35,
                "p4_prediction": false,
                "confidence": "Medium",
                "is_elite": false,
                "model_version": "v1.3"
            }
        },
        "limit": 25  # Optional - max schools to return (default: 50)
    }

    Returns comprehensive school analysis with:
    - School details (name, division, location, size, grades, costs)
    - PROs: What matches user preferences with descriptions
    - CONs: What doesn't match with explanations
    - Must-have filtering summary
    - Nice-to-have preference breakdown
    """
    try:
        # Validate required data
        user_preferences_data = request.get("user_preferences", {})
        ml_data = request.get("ml_results", {})
        limit = request.get("limit", 50)

        if not user_preferences_data:
            raise HTTPException(status_code=400, detail="user_preferences is required")
        if not ml_data:
            raise HTTPException(status_code=400, detail="ml_results is required")
        if not user_preferences_data.get("user_state"):
            raise HTTPException(status_code=400, detail="user_state is required for tuition calculation")

        # Create UserPreferences object with all current fields
        preferences = UserPreferences(
            # Required field
            user_state=user_preferences_data.get("user_state"),

            # Geographic preferences
            preferred_states=user_preferences_data.get("preferred_states"),
            preferred_regions=user_preferences_data.get("preferred_regions"),

            # Academic preferences
            min_academic_rating=user_preferences_data.get("min_academic_rating"),
            min_student_satisfaction_rating=user_preferences_data.get("min_student_satisfaction_rating"),
            gpa=user_preferences_data.get("gpa"),
            sat=user_preferences_data.get("sat"),
            act=user_preferences_data.get("act"),
            intended_major_buckets=user_preferences_data.get("intended_major_buckets"),

            # Financial preferences
            max_budget=user_preferences_data.get("max_budget"),

            # School characteristics
            preferred_school_size=user_preferences_data.get("preferred_school_size"),
            party_scene_preference=user_preferences_data.get("party_scene_preference"),

            # Athletic preferences
            min_athletics_rating=user_preferences_data.get("min_athletics_rating"),

            # Demographic
            hs_graduation_year=user_preferences_data.get("hs_graduation_year")
        )

        # Handle dynamic must-have preferences
        must_have_prefs = user_preferences_data.get("must_have_preferences", [])
        for pref_name in must_have_prefs:
            preferences.make_must_have(pref_name)

        # Create ML results object (simplified - no player object needed for filtering)
        d1_data = ml_data.get("d1_results", {})
        p4_data = ml_data.get("p4_results")

        # Create a minimal player object for ML results structure
        dummy_player = PlayerInfielder(
            height=72, weight=180, exit_velo_max=90, sixty_time=7.0,
            throwing_hand='R', hitting_handedness='R', region='West',
            primary_position='SS', inf_velo=80
        )

        d1_results = D1PredictionResult(
            d1_probability=d1_data.get("d1_probability", 0.0),
            d1_prediction=d1_data.get("d1_prediction", False),
            confidence=d1_data.get("confidence", "Medium"),
            model_version=d1_data.get("model_version", "unknown")
        )

        p4_results = None
        if p4_data:
            p4_results = P4PredictionResult(
                p4_probability=p4_data.get("p4_probability", 0.0),
                p4_prediction=p4_data.get("p4_prediction", False),
                confidence=p4_data.get("confidence", "Medium"),
                is_elite=p4_data.get("is_elite", False),
                model_version=p4_data.get("model_version", "unknown")
            )

        ml_results = MLPipelineResults(
            player=dummy_player,
            d1_results=d1_results,
            p4_results=p4_results
        )

        # Run the async two-tier filtering pipeline
        logger.info(f"Running async school filtering for user from {preferences.user_state}")
        filtering_result = await get_school_matches_shared(preferences, ml_results, limit)

        if not filtering_result or not filtering_result.school_matches:
            return {
                "success": True,
                "message": "No schools found matching your criteria",
                "summary": {
                    "total_matches": 0,
                    "must_have_count": filtering_result.must_have_count if filtering_result else 0,
                    "ml_prediction": ml_results.get_final_prediction()
                },
                "schools": []
            }

        # Format the response with detailed school information
        schools_data = []
        for school_match in filtering_result.school_matches:
            school_info = {
                # Basic school information
                "school_name": school_match.school_name,
                "division_group": school_match.division_group,
                "location": {
                    "state": school_match.school_data.get("school_state"),
                    "region": school_match.school_data.get("school_region")
                },
                "size": {
                    "enrollment": school_match.school_data.get("undergrad_enrollment"),
                    "category": _get_size_category(school_match.school_data.get("undergrad_enrollment", 0))
                },
                "academics": {
                    "grade": school_match.school_data.get("academics_grade"),
                    "avg_sat": school_match.school_data.get("avg_sat"),
                    "avg_act": school_match.school_data.get("avg_act"),
                    "admission_rate": school_match.school_data.get("admission_rate")
                },
                "athletics": {
                    "grade": school_match.school_data.get("total_athletics_grade")
                },
                "student_life": {
                    "grade": school_match.school_data.get("student_life_grade"),
                    "party_scene_grade": school_match.school_data.get("party_scene_grade")
                },
                "financial": {
                    "in_state_tuition": school_match.school_data.get("in_state_tuition"),
                    "out_of_state_tuition": school_match.school_data.get("out_of_state_tuition")
                },
                "overall_grade": school_match.school_data.get("overall_grade"),

                # Matching analysis
                "match_analysis": {
                    "total_nice_to_have_matches": len(school_match.nice_to_have_matches),
                    "pros": [
                        {
                            "preference": match.preference_name,
                            "description": match.description,
                            "category": match.preference_type.value
                        }
                        for match in school_match.nice_to_have_matches
                    ],
                    "cons": [
                        {
                            "preference": miss.preference_name,
                            "reason": miss.reason,
                            "category": miss.preference_type.value
                        }
                        for miss in school_match.nice_to_have_misses
                    ]
                }
            }
            schools_data.append(school_info)

        return {
            "success": True,
            "message": f"Found {len(schools_data)} schools matching your preferences",
            "summary": {
                "total_matches": len(schools_data),
                "must_have_count": filtering_result.must_have_count,
                "ml_prediction": ml_results.get_final_prediction(),
                "d1_probability": ml_results.d1_results.d1_probability,
                "p4_probability": ml_results.p4_results.p4_probability if ml_results.p4_results else None,
                "must_have_preferences": list(preferences.get_must_haves().keys()),
                "nice_to_have_preferences": list(preferences.get_nice_to_haves().keys())
            },
            "schools": schools_data,
            "metadata": {
                "processed_at": datetime.now().isoformat(),
                "pipeline_version": "v2.0",
                "limit_applied": limit
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in school filtering: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/count")
async def count_schools_by_preferences(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    🔢 QUICK COUNT ENDPOINT: Get count of schools meeting must-have requirements

    Perfect for dynamic UI updates as users modify their must-have preferences.
    Much faster than full filtering since it only counts without detailed analysis.

    Expected request format (same as /filter but only uses must-have preferences):
    {
        "user_preferences": { ... },  # Same format as /filter
        "ml_results": { ... }         # Same format as /filter
    }

    Returns:
    {
        "success": true,
        "count": 24,
        "ml_prediction": "Non-P4 D1",
        "must_have_preferences": ["max_budget", "min_academic_rating"]
    }
    """
    try:
        # Parse request (reuse same logic as filter endpoint)
        user_preferences_data = request.get("user_preferences", {})
        ml_data = request.get("ml_results", {})

        if not user_preferences_data or not ml_data:
            raise HTTPException(status_code=400, detail="user_preferences and ml_results are required")

        # Create preferences and ML results (same as filter endpoint)
        preferences = UserPreferences(user_state=user_preferences_data.get("user_state", "CA"))

        # Add all preference fields
        for field, value in user_preferences_data.items():
            if hasattr(preferences, field) and value is not None:
                setattr(preferences, field, value)

        # Handle must-have preferences
        must_have_prefs = user_preferences_data.get("must_have_preferences", [])
        for pref_name in must_have_prefs:
            preferences.make_must_have(pref_name)

        # Create ML results (simplified)
        dummy_player = PlayerInfielder(height=72, weight=180, exit_velo_max=90, sixty_time=7.0,
                                     throwing_hand='R', hitting_handedness='R', region='West',
                                     primary_position='SS', inf_velo=80)

        d1_data = ml_data.get("d1_results", {})
        p4_data = ml_data.get("p4_results")

        ml_results = MLPipelineResults(
            player=dummy_player,
            d1_results=D1PredictionResult(
                d1_probability=d1_data.get("d1_probability", 0.0),
                d1_prediction=d1_data.get("d1_prediction", False),
                confidence=d1_data.get("confidence", "Medium"),
                model_version=d1_data.get("model_version", "unknown")
            ),
            p4_results=P4PredictionResult(
                p4_probability=p4_data.get("p4_probability", 0.0) if p4_data else 0.0,
                p4_prediction=p4_data.get("p4_prediction", False) if p4_data else False,
                confidence=p4_data.get("confidence", "Medium") if p4_data else "Medium",
                is_elite=p4_data.get("is_elite", False) if p4_data else False,
                model_version=p4_data.get("model_version", "unknown") if p4_data else "unknown"
            ) if p4_data else None
        )

        # Get quick count with async pipeline
        count = await count_eligible_schools_shared(preferences, ml_results)

        return {
            "success": True,
            "count": count,
            "ml_prediction": ml_results.get_final_prediction(),
            "must_have_preferences": list(preferences.get_must_haves().keys()),
            "message": f"{count} schools meet your must-have requirements"
        }

    except Exception as e:
        logger.error(f"Error in school counting: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error counting schools: {str(e)}")

def _get_size_category(enrollment: int) -> str:
    """Helper function to categorize school size"""
    if enrollment <= 2999:
        return "Small"
    elif enrollment <= 9999:
        return "Medium"
    elif enrollment <= 29999:
        return "Large"
    else:
        return "Very Large"

@router.get("/example")
async def get_preferences_example() -> Dict[str, Any]:
    """
    📋 Get complete example of preference filtering request

    Returns example with all current preference fields and proper structure
    for both /filter and /count endpoints.
    """
    example_request = {
        "user_preferences": {
            # Required field
            "user_state": "CA",

            # Geographic preferences (multi-select)
            "preferred_states": ["CA", "TX", "FL"],
            "preferred_regions": ["West", "South"],

            # Academic preferences
            "min_academic_rating": "B+",
            "min_student_satisfaction_rating": "B",
            "gpa": 3.5,
            "sat": 1350,
            "act": 30,
            "intended_major_buckets": "Engineering",

            # Financial preferences
            "max_budget": 35000,

            # School characteristics (multi-select)
            "preferred_school_size": ["Medium", "Large"],
            "party_scene_preference": ["Moderate"],

            # Athletic preferences
            "min_athletics_rating": "B+",

            # Demographic
            "hs_graduation_year": "2025",

            # Dynamic must-have marking
            "must_have_preferences": ["max_budget", "min_academic_rating", "preferred_states"]
        },
        "ml_results": {
            "d1_results": {
                "d1_probability": 0.75,
                "d1_prediction": True,
                "confidence": "High",
                "model_version": "v2.1"
            },
            "p4_results": {
                "p4_probability": 0.35,
                "p4_prediction": False,
                "confidence": "Medium",
                "is_elite": False,
                "model_version": "v1.3"
            }
        },
        "limit": 25
    }

    return {
        "description": "Complete school filtering system with two-tier preferences",
        "endpoints": {
            "POST /preferences/filter": "Get detailed school matches with PROs/CONs analysis",
            "POST /preferences/count": "Get quick count of schools meeting must-haves (for UI updates)",
            "GET /preferences/example": "This example endpoint",
            "GET /preferences/health": "Health check"
        },
        "example_request": example_request,
        "features": [
            "Two-tier filtering: must-have vs nice-to-have preferences",
            "Dynamic preference marking: any preference can be marked as must-have",
            "Multi-select support: states, regions, school sizes, party scene",
            "PROs analysis: detailed explanations of what matches",
            "CONs analysis: explanations of what doesn't match and why",
            "ML integration: probability-based school selection across divisions",
            "Financial intelligence: in-state vs out-of-state tuition calculation",
            "Academic fit scoring: SAT/ACT compatibility analysis"
        ],
        "notes": [
            "user_state is required for accurate tuition calculation",
            "must_have_preferences dynamically controls filtering strictness",
            "ML results determine division group selection and overlap",
            "Limit parameter controls maximum schools returned (default: 50)",
            "/count endpoint is optimized for real-time UI updates"
        ]
    }

@router.get("/health")
async def preferences_health_check() -> Dict[str, str]:
    """Health check for preferences router"""
    return {"status": "ok", "service": "school_preferences_filtering"}