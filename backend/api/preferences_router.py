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
from backend.utils.preferences_types import UserPreferences, VALID_GRADES
from backend.utils.prediction_types import MLPipelineResults, D1PredictionResult, P4PredictionResult
from backend.utils.player_types import PlayerInfielder, PlayerOutfielder, PlayerCatcher
from backend.utils.recommendation_types import (
    AcademicsInfo,
    AthleticsInfo,
    FinancialInfo,
    MatchAnalysis,
    MatchMiss,
    MatchPoint,
    PlayingTimeInfo,
    RecommendationSummary,
    SchoolLocation,
    SchoolRecommendation,
    SchoolSize,
    SortScores,
    StudentLifeInfo,
)
try:
    from celery.result import AsyncResult
except Exception:  # pragma: no cover - optional dependency
    AsyncResult = None

try:
    from backend.llm.tasks import (
        generate_llm_reasoning,
        compute_request_hash,
        get_cached_reasoning,
        get_inflight_job_id,
        set_inflight_job_id,
    )
except Exception:  # pragma: no cover - optional dependency
    generate_llm_reasoning = None
    compute_request_hash = None
    get_cached_reasoning = None
    get_inflight_job_id = None
    set_inflight_job_id = None

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
            "sat": 1350,                      # Student's SAT score
            "act": 30,                        # Student's ACT score
            "hs_graduation_year": "2025",     # Graduation year
            "must_have_preferences": ["max_budget", "min_academic_rating"] # Dynamic must-haves
        },
        "player_info": {
            "height": 72,                     # Height in inches
            "weight": 180,                    # Weight in lbs
            "primary_position": "SS",         # Position (1B, 2B, 3B, SS, OF, C)
            "exit_velo_max": 95.0,            # Max exit velocity (mph)
            "sixty_time": 6.85,               # 60-yard dash (seconds)
            "inf_velo": 85.0,                 # Infield throw velo (mph) - for infielders
            "of_velo": null,                  # Outfield throw velo (mph) - for outfielders
            "c_velo": null,                   # Catcher throw velo (mph) - for catchers
            "pop_time": null,                 # Pop time (seconds) - for catchers
            "throwing_hand": "R",             # R or L
            "hitting_handedness": "R",        # R, L, or S
            "region": "West"                  # Player's home region
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
        "limit": 25,  # Optional - max schools to return (default: 50)
        "sort_by": "playing_time_score",  # Optional - playing_time_score | academic_grade | nice_to_have_count
        "sort_order": "desc"  # Optional - asc | desc
    }

    Returns comprehensive school analysis with:
    - School details (name, division, location, size, grades, costs)
    - PROs: What matches user preferences with descriptions
    - CONs: What doesn't match with explanations
    - Playing time analysis: z-score, percentile, bucket, interpretation
    - Must-have filtering summary
    - Nice-to-have preference breakdown
    """
    try:
        # Validate required data
        user_preferences_data = request.get("user_preferences", {})
        player_info = request.get("player_info", {})
        ml_data = request.get("ml_results", {})
        limit = request.get("limit", 50)
        sort_by = request.get("sort_by")
        sort_order = request.get("sort_order", "desc")
        use_llm_reasoning = request.get("use_llm_reasoning", False)

        if not user_preferences_data:
            raise HTTPException(status_code=400, detail="user_preferences is required")
        if not ml_data:
            raise HTTPException(status_code=400, detail="ml_results is required")
        if not user_preferences_data.get("user_state"):
            raise HTTPException(status_code=400, detail="user_state is required for tuition calculation")
        if not player_info:
            raise HTTPException(status_code=400, detail="player_info is required for playing time calculation")

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

        # Create ML results object with player stats for playing time calculation
        d1_data = ml_data.get("d1_results", {})
        p4_data = ml_data.get("p4_results")

        # Create the appropriate player object based on position
        player = _create_player_from_info(player_info)

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
            player=player,
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
        school_recommendations: List[SchoolRecommendation] = []
        for school_match in filtering_result.school_matches:
            playing_time_score = (school_match.playing_time_result.percentile
                                  if school_match.playing_time_result is not None else None)
            nice_to_have_count = len(school_match.nice_to_have_matches)
            academic_grade = school_match.school_data.get("academics_grade")

            school_recommendations.append(
                _build_school_recommendation(
                    school_match,
                    playing_time_score,
                    academic_grade,
                    nice_to_have_count,
                )
            )

        if sort_by:
            school_recommendations = _sort_school_recommendations(
                school_recommendations, sort_by, sort_order
            )

        summary = RecommendationSummary(
            low_result_flag=len(school_recommendations) < 5,
            llm_enabled=bool(use_llm_reasoning),
        )

        if use_llm_reasoning and school_recommendations and generate_llm_reasoning is not None:
            try:
                ml_summary = {
                    "final_prediction": ml_results.get_final_prediction(),
                    "d1_probability": ml_results.d1_results.d1_probability,
                    "p4_probability": ml_results.p4_results.p4_probability if ml_results.p4_results else None,
                    "confidence": ml_results.get_pipeline_confidence(),
                }
                preferences_payload = preferences.to_dict_with_must_haves()
                player_payload = ml_results.get_player_info()

                task_payload = {
                    "schools": [rec.to_dict() for rec in school_recommendations],
                    "player_info": player_payload,
                    "ml_summary": ml_summary,
                    "preferences": preferences_payload,
                    "must_haves": preferences.get_must_haves(),
                    "total_matches": len(school_recommendations),
                    "min_threshold": 5,
                    "include_player_summary": False,
                }
                request_hash = None
                if compute_request_hash is not None:
                    request_hash = compute_request_hash(task_payload)
                    cached = get_cached_reasoning(request_hash) if get_cached_reasoning else None
                    if cached is not None:
                        summary.llm_job_id = request_hash
                        summary.llm_status = "cached"
                    else:
                        inflight = get_inflight_job_id(request_hash) if get_inflight_job_id else None
                        if inflight:
                            summary.llm_job_id = inflight
                            summary.llm_status = "queued"
                        else:
                            task_payload["request_hash"] = request_hash
                            task = generate_llm_reasoning.delay(task_payload)
                            summary.llm_job_id = task.id
                            summary.llm_status = "queued"
                            if set_inflight_job_id:
                                set_inflight_job_id(request_hash, task.id)
                else:
                    task = generate_llm_reasoning.delay(task_payload)
                    summary.llm_job_id = task.id
                    summary.llm_status = "queued"
            except Exception as e:
                logger.error(f"LLM reasoning failed: {str(e)}")
        elif use_llm_reasoning and generate_llm_reasoning is None:
            summary.llm_status = "unavailable"

        return {
            "success": True,
            "message": f"Found {len(school_recommendations)} schools matching your preferences",
            "summary": {
                "total_matches": len(school_recommendations),
                "must_have_count": filtering_result.must_have_count,
                "ml_prediction": ml_results.get_final_prediction(),
                "d1_probability": ml_results.d1_results.d1_probability,
                "p4_probability": ml_results.p4_results.p4_probability if ml_results.p4_results else None,
                "must_have_preferences": list(preferences.get_must_haves().keys()),
                "nice_to_have_preferences": list(preferences.get_nice_to_haves().keys()),
                "sort_by": sort_by,
                "sort_order": sort_order
            },
            "recommendation_summary": summary.to_dict(),
            "schools": [rec.to_dict() for rec in school_recommendations],
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


def _academic_grade_rank(grade: Optional[str]) -> Optional[int]:
    """Convert academic grade to a numeric rank (higher is better)."""
    if grade not in VALID_GRADES:
        return None
    return len(VALID_GRADES) - 1 - VALID_GRADES.index(grade)


def _coerce_sort_value(value: Optional[float], reverse: bool) -> float:
    """Ensure missing values sort last."""
    if value is None:
        return float("-inf") if reverse else float("inf")
    return value


def _sort_school_recommendations(
    schools: List[SchoolRecommendation], sort_by: str, sort_order: str
) -> List[SchoolRecommendation]:
    """Sort school recommendations by a supported score field."""
    reverse = sort_order.lower() != "asc"
    if sort_by == "playing_time_score":
        return sorted(
            schools,
            key=lambda s: _coerce_sort_value(s.scores.playing_time_score, reverse),
            reverse=reverse
        )
    if sort_by == "nice_to_have_count":
        return sorted(
            schools,
            key=lambda s: _coerce_sort_value(s.scores.nice_to_have_count, reverse),
            reverse=reverse
        )
    if sort_by == "academic_grade":
        return sorted(
            schools,
            key=lambda s: _coerce_sort_value(
                _academic_grade_rank(s.scores.academic_grade), reverse
            ),
            reverse=reverse
        )
    return schools


def _format_playing_time(playing_time_result) -> PlayingTimeInfo:
    """Format PlayingTimeResult for SchoolRecommendation."""
    if playing_time_result is None:
        return PlayingTimeInfo(
            available=False,
            message="Playing time analysis not available for this school",
        )

    return PlayingTimeInfo(
        available=True,
        z_score=round(playing_time_result.final_z_score, 2),
        percentile=round(playing_time_result.percentile, 1),
        bucket=playing_time_result.bucket,
        bucket_description=playing_time_result.bucket_description,
        interpretation=playing_time_result.interpretation,
        breakdown={
            "stats_component": round(playing_time_result.stats_breakdown.component_total, 3),
            "physical_component": round(playing_time_result.physical_breakdown.component_total, 3),
            "ml_component": round(playing_time_result.ml_breakdown.component_total, 3),
            "team_fit_bonus": round(playing_time_result.team_fit_breakdown.bonus, 3),
            "trend_bonus": round(playing_time_result.trend_breakdown.bonus, 3),
        },
        player_strength=playing_time_result.stats_breakdown.player_strength.value,
        team_needs=playing_time_result.team_fit_breakdown.team_needs.value,
        program_trend=playing_time_result.trend_breakdown.trend.value,
    )


def _build_school_recommendation(
    school_match,
    playing_time_score: Optional[float],
    academic_grade: Optional[str],
    nice_to_have_count: int,
) -> SchoolRecommendation:
    return SchoolRecommendation(
        school_name=school_match.school_name,
        division_group=school_match.division_group,
        location=SchoolLocation(
            state=school_match.school_data.get("school_state"),
            region=school_match.school_data.get("school_region"),
        ),
        size=SchoolSize(
            enrollment=school_match.school_data.get("undergrad_enrollment"),
            category=_get_size_category(
                school_match.school_data.get("undergrad_enrollment", 0)
            ),
        ),
        academics=AcademicsInfo(
            grade=school_match.school_data.get("academics_grade"),
            avg_sat=school_match.school_data.get("avg_sat"),
            avg_act=school_match.school_data.get("avg_act"),
            admission_rate=school_match.school_data.get("admission_rate"),
        ),
        athletics=AthleticsInfo(
            grade=school_match.school_data.get("total_athletics_grade")
        ),
        student_life=StudentLifeInfo(
            grade=school_match.school_data.get("student_life_grade"),
            party_scene_grade=school_match.school_data.get("party_scene_grade"),
        ),
        financial=FinancialInfo(
            in_state_tuition=school_match.school_data.get("in_state_tuition"),
            out_of_state_tuition=school_match.school_data.get("out_of_state_tuition"),
        ),
        overall_grade=school_match.school_data.get("overall_grade"),
        match_analysis=MatchAnalysis(
            total_nice_to_have_matches=len(school_match.nice_to_have_matches),
            pros=[
                MatchPoint(
                    preference=match.preference_name,
                    description=match.description,
                    category=match.preference_type.value,
                )
                for match in school_match.nice_to_have_matches
            ],
            cons=[
                MatchMiss(
                    preference=miss.preference_name,
                    reason=miss.reason,
                    category=miss.preference_type.value,
                )
                for miss in school_match.nice_to_have_misses
            ],
        ),
        playing_time=_format_playing_time(school_match.playing_time_result),
        scores=SortScores(
            playing_time_score=playing_time_score,
            academic_grade=academic_grade,
            nice_to_have_count=nice_to_have_count,
        ),
    )


def _create_player_from_info(player_info: Dict[str, Any]):
    """
    Create the appropriate PlayerType object based on position.

    Args:
        player_info: Dictionary with player stats including:
            - height, weight, primary_position (required)
            - exit_velo_max, sixty_time (common stats)
            - inf_velo (infielders), of_velo (outfielders), c_velo/pop_time (catchers)
            - throwing_hand, hitting_handedness, region

    Returns:
        PlayerInfielder, PlayerOutfielder, or PlayerCatcher based on position
    """
    position = player_info.get("primary_position", "SS").upper()

    # Common args for all player types
    common_args = {
        "height": player_info.get("height", 72),
        "weight": player_info.get("weight", 180),
        "primary_position": position,
        "throwing_hand": player_info.get("throwing_hand", "R"),
        "hitting_handedness": player_info.get("hitting_handedness", "R"),
        "region": player_info.get("region", "West"),
        "exit_velo_max": player_info.get("exit_velo_max", 90.0),
        "sixty_time": player_info.get("sixty_time", 7.0),
    }

    if position == "C":
        return PlayerCatcher(
            **common_args,
            c_velo=player_info.get("c_velo", 75.0),
            pop_time=player_info.get("pop_time", 2.0),
        )
    elif position in ["OF", "LF", "CF", "RF"]:
        return PlayerOutfielder(
            **common_args,
            of_velo=player_info.get("of_velo", 85.0),
        )
    else:
        # Default to infielder (1B, 2B, 3B, SS, DH, etc.)
        return PlayerInfielder(
            **common_args,
            inf_velo=player_info.get("inf_velo", 80.0),
        )

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
        "player_info": {
            "height": 72,
            "weight": 180,
            "primary_position": "SS",
            "exit_velo_max": 95.0,
            "sixty_time": 6.85,
            "inf_velo": 85.0,
            "of_velo": None,
            "c_velo": None,
            "pop_time": None,
            "throwing_hand": "R",
            "hitting_handedness": "R",
            "region": "West"
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
        "description": "Complete school filtering system with two-tier preferences and playing time analysis",
        "endpoints": {
            "POST /preferences/filter": "Get detailed school matches with PROs/CONs and playing time analysis",
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
            "Playing time analysis: z-score, percentile, and bucket classification",
            "Team fit analysis: player strength vs team needs alignment",
            "Program trend bonus: opportunity assessment based on program trajectory",
            "ML integration: probability-based school selection across divisions",
            "Financial intelligence: in-state vs out-of-state tuition calculation",
            "Academic fit scoring: SAT/ACT compatibility analysis"
        ],
        "notes": [
            "user_state is required for accurate tuition calculation",
            "player_info is required for playing time calculation",
            "must_have_preferences dynamically controls filtering strictness",
            "ML results determine division group selection and overlap",
            "Playing time uses z-scores against division benchmarks",
            "Limit parameter controls maximum schools returned (default: 50)",
            "/count endpoint is optimized for real-time UI updates (no playing time)"
        ]
    }

@router.get("/reasoning/{job_id}")
async def get_llm_reasoning(job_id: str) -> Dict[str, Any]:
    """
    Retrieve LLM reasoning results for a queued recommendation job.
    """
    if AsyncResult is None:
        raise HTTPException(status_code=503, detail="LLM queue unavailable")

    cached = None
    if get_cached_reasoning is not None:
        cached = get_cached_reasoning(job_id)
    if cached is not None:
        return {
            "success": True,
            "job_id": job_id,
            "status": "completed",
            "reasoning": cached.get("reasoning", {}),
            "player_summary": cached.get("player_summary"),
            "relax_suggestions": cached.get("relax_suggestions", []),
            "completed_at": cached.get("completed_at"),
        }

    inflight_id = None
    if get_inflight_job_id is not None:
        inflight_id = get_inflight_job_id(job_id)

    result = AsyncResult(inflight_id or job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if not result.ready():
        return {
            "success": True,
            "job_id": job_id,
            "status": result.status.lower(),
            "reasoning": None,
            "player_summary": None,
            "relax_suggestions": [],
        }

    if result.failed():
        return {
            "success": False,
            "job_id": job_id,
            "status": "failed",
            "reasoning": None,
            "player_summary": None,
            "relax_suggestions": [],
        }

    payload = result.result or {}
    return {
        "success": True,
        "job_id": job_id,
        "status": "completed",
        "reasoning": payload.get("reasoning", {}),
        "player_summary": payload.get("player_summary"),
        "relax_suggestions": payload.get("relax_suggestions", []),
        "completed_at": payload.get("completed_at"),
    }

@router.get("/health")
async def preferences_health_check() -> Dict[str, str]:
    """Health check for preferences router"""
    return {"status": "ok", "service": "school_preferences_filtering"}
