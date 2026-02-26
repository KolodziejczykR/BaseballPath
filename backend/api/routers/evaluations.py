"""
Authenticated evaluation orchestration endpoints.

This router runs ML prediction + school filtering, enforces plan quotas, and persists
the full evaluation result for the authenticated user.
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..clients.supabase import require_supabase_admin_client
from ..deps.auth import AuthenticatedUser, get_current_user
from ..services.plan_service import (
    enforce_evaluation_quota,
    get_effective_plan,
    get_profile,
    increment_usage,
    remaining_evaluations,
)
from .preferences import filter_schools_by_preferences

from backend.ml.router.infielder_router import InfielderInput
from backend.ml.router.infielder_router import pipeline as infielder_pipeline
from backend.ml.router.outfielder_router import OutfielderInput
from backend.ml.router.outfielder_router import pipeline as outfielder_pipeline
from backend.ml.router.pitcher_router import PitcherInput
from backend.ml.router.pitcher_router import pipeline as pitcher_pipeline
from backend.utils.player_types import PlayerInfielder, PlayerOutfielder, PlayerPitcher

router = APIRouter()


class EvaluationRunRequest(BaseModel):
    position_endpoint: Literal["pitcher", "infielder", "outfielder"]
    identity_input: Dict[str, Any]
    stats_input: Dict[str, Any]
    preferences_input: Dict[str, Any]
    prediction_payload: Dict[str, Any]
    preferences_payload: Dict[str, Any]
    use_llm_reasoning: bool = False


def _run_prediction(position_endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if position_endpoint == "pitcher":
        if pitcher_pipeline is None:
            raise HTTPException(status_code=500, detail="Pitcher pipeline not available")
        validated = PitcherInput(**payload).model_dump(exclude_none=True)
        player = PlayerPitcher(
            height=validated["height"],
            weight=validated["weight"],
            primary_position=validated["primary_position"],
            throwing_hand=validated.get("throwing_hand", "R"),
            region=validated["player_region"],
            fastball_velo_range=validated.get("fastball_velo_range"),
            fastball_velo_max=validated.get("fastball_velo_max"),
            fastball_spin=validated.get("fastball_spin"),
            changeup_velo=validated.get("changeup_velo"),
            changeup_spin=validated.get("changeup_spin"),
            curveball_velo=validated.get("curveball_velo"),
            curveball_spin=validated.get("curveball_spin"),
            slider_velo=validated.get("slider_velo"),
            slider_spin=validated.get("slider_spin"),
        )
        return pitcher_pipeline.predict(player).get_api_response()

    if position_endpoint == "outfielder":
        if outfielder_pipeline is None:
            raise HTTPException(status_code=500, detail="Outfielder pipeline not available")
        validated = OutfielderInput(**payload).model_dump(exclude_none=True)
        player = PlayerOutfielder(
            height=validated["height"],
            weight=validated["weight"],
            primary_position=validated["primary_position"],
            hitting_handedness=validated["hitting_handedness"],
            throwing_hand=validated["throwing_hand"],
            region=validated["player_region"],
            exit_velo_max=validated["exit_velo_max"],
            of_velo=validated["of_velo"],
            sixty_time=validated["sixty_time"],
        )
        return outfielder_pipeline.predict(player).get_api_response()

    if position_endpoint == "infielder":
        if infielder_pipeline is None:
            raise HTTPException(status_code=500, detail="Infielder pipeline not available")
        validated = InfielderInput(**payload).model_dump(exclude_none=True)
        player = PlayerInfielder(
            height=validated["height"],
            weight=validated["weight"],
            primary_position=validated["primary_position"],
            hitting_handedness=validated["hitting_handedness"],
            throwing_hand=validated["throwing_hand"],
            region=validated["player_region"],
            exit_velo_max=validated["exit_velo_max"],
            inf_velo=validated["inf_velo"],
            sixty_time=validated["sixty_time"],
        )
        return infielder_pipeline.predict(player).get_api_response()

    raise HTTPException(status_code=400, detail=f"Unsupported position_endpoint: {position_endpoint}")


def _ml_results_from_prediction(prediction_response: Dict[str, Any]) -> Dict[str, Any]:
    d1_details = prediction_response.get("d1_details") or {}
    p4_details = prediction_response.get("p4_details")
    return {
        "d1_results": {
            "d1_probability": d1_details.get("probability", prediction_response.get("d1_probability", 0)),
            "d1_prediction": d1_details.get("prediction", False),
            "confidence": d1_details.get("confidence", "Medium"),
            "model_version": d1_details.get("model_version", "unknown"),
        },
        "p4_results": (
            {
                "p4_probability": p4_details.get("probability", prediction_response.get("p4_probability", 0)),
                "p4_prediction": p4_details.get("prediction", False),
                "confidence": p4_details.get("confidence", "Medium"),
                "is_elite": p4_details.get("is_elite", False),
                "model_version": p4_details.get("model_version", "unknown"),
            }
            if p4_details
            else None
        ),
    }


def _extract_top_schools(preferences_response: Dict[str, Any], limit: int = 3) -> Any:
    schools = preferences_response.get("schools") or []
    return schools[:limit]


def _persist_evaluation_run(
    *,
    user_id: str,
    payload: EvaluationRunRequest,
    prediction_response: Dict[str, Any],
    preferences_response: Dict[str, Any],
) -> str:
    supabase = require_supabase_admin_client()
    recommendation_summary = preferences_response.get("recommendation_summary") or {}
    llm_job_id = recommendation_summary.get("llm_job_id")
    llm_status = recommendation_summary.get("llm_status")

    insert_payload = {
        "user_id": user_id,
        "position_track": payload.position_endpoint,
        "identity_input": payload.identity_input,
        "stats_input": payload.stats_input,
        "preferences_input": payload.preferences_input,
        "prediction_response": prediction_response,
        "preferences_response": preferences_response,
        "top_schools_snapshot": _extract_top_schools(preferences_response),
        "llm_reasoning_status": llm_status,
        "llm_job_id": llm_job_id,
    }
    response = (
        supabase.table("prediction_runs")
        .insert(insert_payload)
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist evaluation run",
        )
    run = response.data[0]
    run_id = run.get("id")
    if not run_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Persisted evaluation run did not return an id",
        )
    return str(run_id)


@router.post("/run")
async def run_evaluation(
    payload: EvaluationRunRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    # Ensure profile exists for every authenticated user
    _ = get_profile(current_user.user_id, current_user.email)

    effective_plan = get_effective_plan(current_user.user_id)
    usage_before = enforce_evaluation_quota(current_user.user_id, effective_plan)

    if payload.use_llm_reasoning and not effective_plan.llm_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "llm_reasoning_not_available_for_plan",
                "plan_tier": effective_plan.plan_tier,
            },
        )

    prediction_response = _run_prediction(payload.position_endpoint, payload.prediction_payload)

    preferences_payload = dict(payload.preferences_payload)
    preferences_payload["ml_results"] = _ml_results_from_prediction(prediction_response)
    if payload.use_llm_reasoning:
        preferences_payload["use_llm_reasoning"] = True
    else:
        preferences_payload.pop("use_llm_reasoning", None)

    preferences_response = await filter_schools_by_preferences(preferences_payload)

    run_id = _persist_evaluation_run(
        user_id=current_user.user_id,
        payload=payload,
        prediction_response=prediction_response,
        preferences_response=preferences_response,
    )

    usage_after = increment_usage(
        current_user.user_id,
        evaluation_increment=1,
        llm_increment=1 if payload.use_llm_reasoning else 0,
    )

    return {
        "run_id": run_id,
        "prediction_response": prediction_response,
        "preferences_response": preferences_response,
        "entitlement": {
            "plan_tier": effective_plan.plan_tier,
            "monthly_eval_limit": effective_plan.monthly_eval_limit,
            "remaining_evals": remaining_evaluations(effective_plan, usage_after),
            "usage_before": usage_before.eval_count,
            "usage_after": usage_after.eval_count,
        },
    }


@router.get("")
async def list_evaluations(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    supabase = require_supabase_admin_client()
    end_index = offset + limit - 1
    response = (
        supabase.table("prediction_runs")
        .select("*", count="exact")
        .eq("user_id", current_user.user_id)
        .order("created_at", desc=True)
        .range(offset, end_index)
        .execute()
    )
    return {
        "items": response.data or [],
        "limit": limit,
        "offset": offset,
        "total": response.count if hasattr(response, "count") else None,
    }


@router.get("/{run_id}")
async def get_evaluation(
    run_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    supabase = require_supabase_admin_client()
    response = (
        supabase.table("prediction_runs")
        .select("*")
        .eq("id", run_id)
        .eq("user_id", current_user.user_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return response.data[0]
