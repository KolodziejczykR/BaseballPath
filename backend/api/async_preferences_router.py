"""
Async School Preferences and Filtering Router for BaseballPATH
API endpoints for user preference-based school filtering with two-tier system
Enhanced with async operations, connection pooling, and concurrency control
"""

import asyncio
import time
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

# Import the async filtering pipeline and required types
import os
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.school_filtering.async_two_tier_pipeline import (
    get_school_matches_shared, count_eligible_schools_shared, get_global_async_pipeline
)
from backend.utils.preferences_types import UserPreferences, VALID_GRADES
from backend.utils.prediction_types import MLPipelineResults, D1PredictionResult, P4PredictionResult
from backend.utils.player_types import PlayerInfielder, PlayerOutfielder, PlayerCatcher

router = APIRouter()
logger = logging.getLogger(__name__)

# Concurrency control
CONCURRENT_REQUEST_LIMIT = 10  # Maximum concurrent filtering requests
request_semaphore = asyncio.Semaphore(CONCURRENT_REQUEST_LIMIT)

# Request tracking for monitoring
active_requests = {}
request_stats = {
    'total_requests': 0,
    'successful_requests': 0,
    'failed_requests': 0,
    'average_response_time': 0.0,
    'concurrent_limit_hits': 0
}


async def get_request_limiter():
    """Dependency for request rate limiting"""
    try:
        async with request_semaphore:
            yield
    except asyncio.TimeoutError:
        request_stats['concurrent_limit_hits'] += 1
        raise HTTPException(
            status_code=429,
            detail="Too many concurrent requests. Please try again later."
        )


@router.post("/filter")
async def filter_schools_by_preferences_async(
    request: Dict[str, Any],
    background_tasks: BackgroundTasks,
    _: None = Depends(get_request_limiter)
) -> Dict[str, Any]:
    """
    🎯 ASYNC MAIN ENDPOINT: Filter schools based on user preferences and ML predictions

    Enhanced with async operations, connection pooling, and improved concurrency handling.
    Provides the same functionality as the sync version but with better performance under load.

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
        "limit": 25,  # Optional - max schools to return (default: 50)
        "sort_by": "playing_time_score",  # Optional - playing_time_score | academic_grade | nice_to_have_count
        "sort_order": "desc"  # Optional - asc | desc
    }

    Returns comprehensive school analysis with enhanced performance metrics.
    """
    request_id = f"filter_{int(time.time() * 1000)}"
    start_time = time.time()

    try:
        # Track active request
        active_requests[request_id] = {
            'start_time': start_time,
            'endpoint': 'filter',
            'status': 'processing'
        }

        request_stats['total_requests'] += 1
        logger.info(f"🎯 Starting async school filtering request {request_id}")

        # Validate required data
        user_preferences_data = request.get("user_preferences", {})
        ml_data = request.get("ml_results", {})
        limit = request.get("limit", 50)
        sort_by = request.get("sort_by")
        sort_order = request.get("sort_order", "desc")

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
            sat=user_preferences_data.get("sat"),
            act=user_preferences_data.get("act"),
            admit_rate_floor=user_preferences_data.get("admit_rate_floor"),

            # Financial preferences
            max_budget=user_preferences_data.get("max_budget"),

            # School characteristics
            preferred_school_size=user_preferences_data.get("preferred_school_size"),
            party_scene_preference=user_preferences_data.get("party_scene_preference"),
            min_student_satisfaction_rating=user_preferences_data.get("min_student_satisfaction_rating"),

            # Athletic preferences
            min_athletics_rating=user_preferences_data.get("min_athletics_rating"),

            # Additional preferences
            intended_major_buckets=user_preferences_data.get("intended_major_buckets"),
            hs_graduation_year=user_preferences_data.get("hs_graduation_year"),

            # Dynamic must-have preferences
            must_have_preferences=set(user_preferences_data.get("must_have_preferences", []))
        )

        # Create ML results object
        d1_data = ml_data.get("d1_results", {})
        p4_data = ml_data.get("p4_results")

        d1_results = D1PredictionResult(
            d1_probability=d1_data.get("d1_probability", 0.0),
            d1_prediction=d1_data.get("d1_prediction", False),
            confidence=d1_data.get("confidence", "Unknown"),
            model_version=d1_data.get("model_version", "unknown")
        )

        p4_results = None
        if p4_data:
            p4_results = P4PredictionResult(
                p4_probability=p4_data.get("p4_probability", 0.0),
                p4_prediction=p4_data.get("p4_prediction", False),
                confidence=p4_data.get("confidence", "Unknown"),
                is_elite=p4_data.get("is_elite", False),
                model_version=p4_data.get("model_version", "unknown")
            )

        # Create a dummy player for ML results (required by the structure)
        dummy_player = PlayerInfielder(
            height=70, weight=180, exit_velo_max=85, sixty_time=7.0,
            throwing_hand='R', hitting_handedness='R', region='Unknown',
            primary_position='Unknown', inf_velo=80
        )

        ml_results = MLPipelineResults(
            player=dummy_player,
            d1_results=d1_results,
            p4_results=p4_results
        )

        # Perform async school filtering with shared connection
        logger.info(f"🔍 Processing {limit} schools with async pipeline for request {request_id}")

        filtering_result = await get_school_matches_shared(preferences, ml_results, limit)

        # Prepare response
        school_matches_data = []
        for school_match in filtering_result.school_matches:
            # Convert NiceToHaveMatch and NiceToHaveMiss objects to dictionaries
            pros = []
            for match in school_match.nice_to_have_matches:
                pros.append({
                    "preference_type": match.preference_type.value,
                    "preference_name": match.preference_name,
                    "user_value": match.user_value,
                    "school_value": match.school_value,
                    "description": match.description
                })

            cons = []
            for miss in school_match.nice_to_have_misses:
                cons.append({
                    "preference_type": miss.preference_type.value,
                    "preference_name": miss.preference_name,
                    "user_value": miss.user_value,
                    "school_value": miss.school_value,
                    "reason": miss.reason
                })

            playing_time_score = (school_match.playing_time_result.percentile
                                  if school_match.playing_time_result is not None else None)
            nice_to_have_count = len(school_match.nice_to_have_matches)
            academic_grade = school_match.school_data.get("academics_grade")

            school_data = {
                "school_name": school_match.school_name,
                "division_group": school_match.division_group,
                "school_details": school_match.school_data,
                "pros": pros,
                "cons": cons,
                "nice_to_have_score": nice_to_have_count,
                "total_preferences_evaluated": len(pros) + len(cons),
                "scores": {
                    "playing_time_score": playing_time_score,
                    "academic_grade": academic_grade,
                    "nice_to_have_count": nice_to_have_count,
                }
            }
            school_matches_data.append(school_data)

        if sort_by:
            school_matches_data = _sort_schools(school_matches_data, sort_by, sort_order)

        end_time = time.time()
        processing_time = end_time - start_time

        # Update request tracking
        active_requests[request_id]['status'] = 'completed'
        active_requests[request_id]['processing_time'] = processing_time

        # Update stats
        request_stats['successful_requests'] += 1
        request_stats['average_response_time'] = (
            (request_stats['average_response_time'] * (request_stats['successful_requests'] - 1) + processing_time) /
            request_stats['successful_requests']
        )

        response = {
            "status": "success",
            "request_id": request_id,
            "processing_time_seconds": round(processing_time, 3),
            "schools": school_matches_data,
            "summary": {
                "total_schools_returned": len(school_matches_data),
                "must_have_count": filtering_result.must_have_count,
                "total_schools_considered": filtering_result.total_schools_considered,
                "preferences_summary": {
                    "must_have_preferences": list(preferences.get_must_have_list()),
                    "nice_to_have_preferences": list(preferences.get_nice_to_haves().keys())
                },
                "sort_by": sort_by,
                "sort_order": sort_order
            },
            "performance_metrics": {
                "async_processing": True,
                "connection_pooling": True,
                "concurrent_requests_active": len(active_requests)
            }
        }

        logger.info(f"✅ Async filtering completed for request {request_id} in {processing_time:.3f}s")

        # Schedule cleanup in background
        background_tasks.add_task(cleanup_request_tracking, request_id)

        return response

    except HTTPException:
        raise
    except Exception as e:
        # Update tracking
        if request_id in active_requests:
            active_requests[request_id]['status'] = 'failed'
            active_requests[request_id]['error'] = str(e)

        request_stats['failed_requests'] += 1
        logger.error(f"❌ Error in async school filtering request {request_id}: {e}")

        raise HTTPException(
            status_code=500,
            detail=f"School filtering failed: {str(e)}"
        )


@router.post("/count")
async def count_schools_by_preferences_async(
    request: Dict[str, Any],
    _: None = Depends(get_request_limiter)
) -> Dict[str, Any]:
    """
    📊 ASYNC COUNT ENDPOINT: Quick count of schools meeting must-have requirements

    Enhanced async version for fast UI updates with improved performance.
    """
    request_id = f"count_{int(time.time() * 1000)}"
    start_time = time.time()

    try:
        active_requests[request_id] = {
            'start_time': start_time,
            'endpoint': 'count',
            'status': 'processing'
        }

        request_stats['total_requests'] += 1
        logger.info(f"📊 Starting async school count request {request_id}")

        # Validate required data (same validation as filter endpoint)
        user_preferences_data = request.get("user_preferences", {})
        ml_data = request.get("ml_results", {})

        if not user_preferences_data:
            raise HTTPException(status_code=400, detail="user_preferences is required")
        if not ml_data:
            raise HTTPException(status_code=400, detail="ml_results is required")
        if not user_preferences_data.get("user_state"):
            raise HTTPException(status_code=400, detail="user_state is required")

        # Create preferences and ML results (same as filter endpoint)
        preferences = UserPreferences(
            user_state=user_preferences_data.get("user_state"),
            preferred_states=user_preferences_data.get("preferred_states"),
            preferred_regions=user_preferences_data.get("preferred_regions"),
            min_academic_rating=user_preferences_data.get("min_academic_rating"),
            sat=user_preferences_data.get("sat"),
            act=user_preferences_data.get("act"),
            admit_rate_floor=user_preferences_data.get("admit_rate_floor"),
            max_budget=user_preferences_data.get("max_budget"),
            preferred_school_size=user_preferences_data.get("preferred_school_size"),
            party_scene_preference=user_preferences_data.get("party_scene_preference"),
            min_student_satisfaction_rating=user_preferences_data.get("min_student_satisfaction_rating"),
            min_athletics_rating=user_preferences_data.get("min_athletics_rating"),
            intended_major_buckets=user_preferences_data.get("intended_major_buckets"),
            hs_graduation_year=user_preferences_data.get("hs_graduation_year"),
            must_have_preferences=set(user_preferences_data.get("must_have_preferences", []))
        )

        # Create ML results
        d1_data = ml_data.get("d1_results", {})
        p4_data = ml_data.get("p4_results")

        d1_results = D1PredictionResult(
            d1_probability=d1_data.get("d1_probability", 0.0),
            d1_prediction=d1_data.get("d1_prediction", False),
            confidence=d1_data.get("confidence", "Unknown"),
            model_version=d1_data.get("model_version", "unknown")
        )

        p4_results = None
        if p4_data:
            p4_results = P4PredictionResult(
                p4_probability=p4_data.get("p4_probability", 0.0),
                p4_prediction=p4_data.get("p4_prediction", False),
                confidence=p4_data.get("confidence", "Unknown"),
                is_elite=p4_data.get("is_elite", False),
                model_version=p4_data.get("model_version", "unknown")
            )

        dummy_player = PlayerInfielder(
            height=70, weight=180, exit_velo_max=85, sixty_time=7.0,
            throwing_hand='R', hitting_handedness='R', region='Unknown',
            primary_position='Unknown', inf_velo=80
        )

        ml_results = MLPipelineResults(
            player=dummy_player,
            d1_results=d1_results,
            p4_results=p4_results
        )

        # Perform async count with shared connection
        count = await count_eligible_schools_shared(preferences, ml_results)

        end_time = time.time()
        processing_time = end_time - start_time

        # Update tracking
        active_requests[request_id]['status'] = 'completed'
        active_requests[request_id]['processing_time'] = processing_time

        request_stats['successful_requests'] += 1

        response = {
            "status": "success",
            "request_id": request_id,
            "processing_time_seconds": round(processing_time, 3),
            "count": count,
            "must_have_preferences": list(preferences.get_must_have_list()),
            "performance_metrics": {
                "async_processing": True,
                "connection_pooling": True
            }
        }

        logger.info(f"✅ Async count completed for request {request_id}: {count} schools in {processing_time:.3f}s")
        return response

    except HTTPException:
        raise
    except Exception as e:
        if request_id in active_requests:
            active_requests[request_id]['status'] = 'failed'
            active_requests[request_id]['error'] = str(e)

        request_stats['failed_requests'] += 1
        logger.error(f"❌ Error in async school count request {request_id}: {e}")

        raise HTTPException(
            status_code=500,
            detail=f"School counting failed: {str(e)}"
        )


@router.get("/health")
async def health_check_async() -> Dict[str, Any]:
    """
    🏥 ASYNC HEALTH CHECK: Comprehensive system health with connection pool status
    """
    try:
        start_time = time.time()

        # Get pipeline health
        pipeline = await get_global_async_pipeline()
        pipeline_health = await pipeline.health_check()

        health_check_time = time.time() - start_time

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "async-v1.0",
            "health_check_time_seconds": round(health_check_time, 3),
            "async_features": {
                "connection_pooling": True,
                "circuit_breaker": True,
                "retry_logic": True,
                "concurrent_request_limit": CONCURRENT_REQUEST_LIMIT
            },
            "request_stats": request_stats,
            "active_requests": len(active_requests),
            "pipeline_health": pipeline_health
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
            "request_stats": request_stats
        }


@router.get("/stats")
async def get_performance_stats() -> Dict[str, Any]:
    """
    📈 PERFORMANCE STATS: Real-time performance and concurrency metrics
    """
    try:
        pipeline = await get_global_async_pipeline()
        pipeline_health = await pipeline.health_check()

        return {
            "request_statistics": request_stats,
            "active_requests": {
                "count": len(active_requests),
                "details": list(active_requests.values())
            },
            "concurrency": {
                "max_concurrent_requests": CONCURRENT_REQUEST_LIMIT,
                "available_slots": request_semaphore._value,
                "active_slots": CONCURRENT_REQUEST_LIMIT - request_semaphore._value
            },
            "database_connection_pool": pipeline_health.get('base_pipeline_health', {}).get('database_health', {}).get('connection_stats', {}),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Stats retrieval failed: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


async def cleanup_request_tracking(request_id: str):
    """Background task to clean up completed request tracking"""
    await asyncio.sleep(300)  # Clean up after 5 minutes
    if request_id in active_requests:
        del active_requests[request_id]


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


def _sort_schools(schools: List[Dict[str, Any]], sort_by: str, sort_order: str) -> List[Dict[str, Any]]:
    """Sort schools by a supported score field."""
    reverse = sort_order.lower() != "asc"
    if sort_by == "playing_time_score":
        return sorted(
            schools,
            key=lambda s: _coerce_sort_value(s.get("scores", {}).get("playing_time_score"), reverse),
            reverse=reverse
        )
    if sort_by == "nice_to_have_count":
        return sorted(
            schools,
            key=lambda s: _coerce_sort_value(s.get("scores", {}).get("nice_to_have_count"), reverse),
            reverse=reverse
        )
    if sort_by == "academic_grade":
        return sorted(
            schools,
            key=lambda s: _coerce_sort_value(
                _academic_grade_rank(s.get("scores", {}).get("academic_grade")), reverse
            ),
            reverse=reverse
        )
    return schools


@router.get("/example")
async def get_example_request() -> Dict[str, Any]:
    """
    📋 EXAMPLE REQUEST: Sample request format for async endpoints
    """
    return {
        "message": "Example request format for async school filtering endpoints",
        "endpoints": {
            "/filter": "POST - Async comprehensive school filtering with PROs/CONs",
            "/count": "POST - Async quick count of eligible schools",
            "/health": "GET - Async system health check",
            "/stats": "GET - Real-time performance statistics"
        },
        "example_request": {
            "user_preferences": {
                "user_state": "CA",
                "preferred_states": ["CA", "TX", "FL"],
                "preferred_regions": ["West", "South"],
                "preferred_school_size": ["Medium", "Large"],
                "max_budget": 35000,
                "min_academic_rating": "B+",
                "min_athletics_rating": "B",
                "min_student_satisfaction_rating": "B+",
                "party_scene_preference": ["Moderate"],
                "sat": 1350,
                "act": 30,
                "intended_major_buckets": "Engineering",
                "hs_graduation_year": "2025",
                "must_have_preferences": ["max_budget", "min_academic_rating", "user_state"]
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
            "limit": 25,
            "sort_by": "playing_time_score",
            "sort_order": "desc"
        },
        "async_features": {
            "connection_pooling": "Reuses database connections for better performance",
            "retry_logic": "Automatic retry with exponential backoff",
            "circuit_breaker": "Prevents cascade failures",
            "concurrency_control": f"Maximum {CONCURRENT_REQUEST_LIMIT} concurrent requests",
            "background_tasks": "Non-blocking cleanup operations"
        }
    }
