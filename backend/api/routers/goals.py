"""
Authenticated goals and progress endpoints.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..clients.supabase import require_supabase_admin_client
from ..deps.auth import AuthenticatedUser, get_current_user
from ..services.sensitivity_service import compute_sensitivity
from backend.utils.perturbable_stats import get_perturbable_stats

router = APIRouter()

TARGET_LEVELS = {"D1", "Power 4 D1"}
POSITION_TRACKS = {"pitcher", "infielder", "outfielder", "catcher"}


class GoalCreateRequest(BaseModel):
    position_track: Literal["pitcher", "infielder", "outfielder", "catcher"]
    target_level: str = "D1"
    current_stats: Dict[str, float]
    identity_fields: Dict[str, Any]
    evaluation_run_id: Optional[str] = None


class GoalUpdateRequest(BaseModel):
    target_level: Optional[str] = None
    target_stats: Optional[Dict[str, float]] = None


class ProgressEntryRequest(BaseModel):
    stat_name: str = Field(min_length=1, max_length=120)
    stat_value: float
    source: str = Field(default="manual", max_length=40)
    evaluation_run_id: Optional[str] = None


def _goal_for_user(goal_id: str, user_id: str) -> Dict[str, Any]:
    supabase = require_supabase_admin_client()
    response = (
        supabase.table("player_goals")
        .select("*")
        .eq("id", goal_id)
        .eq("user_id", user_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    return response.data[0]


def _goal_and_progress(goal_id: str, user_id: str) -> Dict[str, Any]:
    goal = _goal_for_user(goal_id, user_id)
    supabase = require_supabase_admin_client()
    progress_response = (
        supabase.table("stat_progress_entries")
        .select("*")
        .eq("goal_id", goal_id)
        .eq("user_id", user_id)
        .order("recorded_at", desc=True)
        .execute()
    )
    return {**goal, "progress_entries": progress_response.data or []}


def _normalize_target_level(level: str) -> str:
    normalized = level.strip()
    if normalized not in TARGET_LEVELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"target_level must be one of {sorted(TARGET_LEVELS)}",
        )
    return normalized


def _normalize_position_track(position_track: str) -> str:
    normalized = position_track.strip().lower()
    if normalized not in POSITION_TRACKS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"position_track must be one of {sorted(POSITION_TRACKS)}",
        )
    return normalized


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _to_float_map(stats: Dict[str, Any]) -> Dict[str, float]:
    normalized: Dict[str, float] = {}
    for key, value in stats.items():
        try:
            normalized[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return normalized


def _resolve_goal_seed_data(
    *,
    payload: GoalCreateRequest,
    user_id: str,
) -> tuple[Dict[str, float], Dict[str, Any]]:
    current_stats = _to_float_map(payload.current_stats)
    identity_fields = _as_dict(payload.identity_fields)
    if not payload.evaluation_run_id:
        return current_stats, identity_fields

    supabase = require_supabase_admin_client()
    eval_response = (
        supabase.table("prediction_runs")
        .select("*")
        .eq("id", payload.evaluation_run_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not eval_response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")
    run = eval_response.data[0]

    if not current_stats:
        current_stats = _to_float_map(_as_dict(run.get("stats_input")))
    if not identity_fields:
        identity_fields = _as_dict(run.get("identity_input"))

    return current_stats, identity_fields


@router.post("")
async def create_goal(
    payload: GoalCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    position_track = _normalize_position_track(payload.position_track)
    target_level = _normalize_target_level(payload.target_level)
    current_stats, identity_fields = _resolve_goal_seed_data(payload=payload, user_id=current_user.user_id)

    if not current_stats:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="current_stats is required")

    supabase = require_supabase_admin_client()
    response = (
        supabase.table("player_goals")
        .insert(
            {
                "user_id": current_user.user_id,
                "position_track": position_track,
                "target_level": target_level,
                "current_stats": current_stats,
                "identity_fields": identity_fields,
                "target_stats": None,
                "sensitivity_results": None,
                "sensitivity_computed_at": None,
                "is_active": True,
            }
        )
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create goal")
    return response.data[0]


@router.get("")
async def list_goals(current_user: AuthenticatedUser = Depends(get_current_user)) -> Dict[str, Any]:
    supabase = require_supabase_admin_client()
    response = (
        supabase.table("player_goals")
        .select("*")
        .eq("user_id", current_user.user_id)
        .eq("is_active", True)
        .order("updated_at", desc=True)
        .execute()
    )

    items = response.data or []
    summaries = []
    for goal in items:
        sensitivity = _as_dict(goal.get("sensitivity_results"))
        rankings = sensitivity.get("rankings") if isinstance(sensitivity.get("rankings"), list) else []
        top_leverage = rankings[0] if rankings else None
        summaries.append(
            {
                **goal,
                "summary": {
                    "current_probability": sensitivity.get("base_probability"),
                    "top_leverage_stat": top_leverage.get("stat_name") if isinstance(top_leverage, dict) else None,
                    "top_leverage_display": top_leverage.get("display") if isinstance(top_leverage, dict) else None,
                },
            }
        )

    return {"items": summaries}


@router.get("/ranges/{position}/{level}")
async def get_stat_ranges(
    position: str,
    level: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    _ = current_user
    position_track = _normalize_position_track(position)
    target_level = _normalize_target_level(level)
    supabase = require_supabase_admin_client()
    response = (
        supabase.table("position_stat_ranges")
        .select("*")
        .eq("position_track", position_track)
        .eq("level", target_level)
        .order("stat_name")
        .execute()
    )
    return {
        "position_track": position_track,
        "level": target_level,
        "items": response.data or [],
    }


@router.get("/{goal_id}")
async def get_goal(goal_id: str, current_user: AuthenticatedUser = Depends(get_current_user)) -> Dict[str, Any]:
    return _goal_and_progress(goal_id, current_user.user_id)


@router.patch("/{goal_id}")
async def update_goal(
    goal_id: str,
    payload: GoalUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    goal = _goal_for_user(goal_id, current_user.user_id)
    updates = {key: value for key, value in payload.model_dump().items() if value is not None}
    if "target_level" in updates:
        updates["target_level"] = _normalize_target_level(str(updates["target_level"]))
    if "target_stats" in updates:
        updates["target_stats"] = _to_float_map(_as_dict(updates.get("target_stats")))

    if not updates:
        return goal

    supabase = require_supabase_admin_client()
    response = (
        supabase.table("player_goals")
        .update(updates)
        .eq("id", goal_id)
        .eq("user_id", current_user.user_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Goal update failed")
    return response.data[0]


@router.post("/{goal_id}/progress")
async def log_progress(
    goal_id: str,
    payload: ProgressEntryRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    goal = _goal_for_user(goal_id, current_user.user_id)

    source = payload.source.strip().lower()
    if source not in {"manual", "evaluation", "verified"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid source")

    supabase = require_supabase_admin_client()
    entry_response = (
        supabase.table("stat_progress_entries")
        .insert(
            {
                "goal_id": goal_id,
                "user_id": current_user.user_id,
                "stat_name": payload.stat_name.strip(),
                "stat_value": payload.stat_value,
                "source": source,
                "evaluation_run_id": payload.evaluation_run_id,
            }
        )
        .execute()
    )
    if not entry_response.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to log progress")

    current_stats = _to_float_map(_as_dict(goal.get("current_stats")))
    current_stats[payload.stat_name.strip()] = float(payload.stat_value)

    goal_update_response = (
        supabase.table("player_goals")
        .update(
            {
                "current_stats": current_stats,
                "sensitivity_results": None,
                "sensitivity_computed_at": None,
            }
        )
        .eq("id", goal_id)
        .eq("user_id", current_user.user_id)
        .execute()
    )
    if not goal_update_response.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update goal stats")

    return {
        "entry": entry_response.data[0],
        "goal": goal_update_response.data[0],
    }


@router.get("/{goal_id}/sensitivity")
async def get_sensitivity(goal_id: str, current_user: AuthenticatedUser = Depends(get_current_user)) -> Dict[str, Any]:
    goal = _goal_for_user(goal_id, current_user.user_id)

    computed_at_raw = goal.get("sensitivity_computed_at")
    cached_results = goal.get("sensitivity_results")
    if computed_at_raw and cached_results:
        computed_at = datetime.fromisoformat(str(computed_at_raw).replace("Z", "+00:00"))
        if computed_at.tzinfo is None:
            computed_at = computed_at.replace(tzinfo=UTC)
        if datetime.now(tz=UTC) - computed_at <= timedelta(hours=24):
            return {
                "cached": True,
                "computed_at": computed_at.isoformat(),
                "results": cached_results,
            }

    position_track = _normalize_position_track(str(goal.get("position_track")))
    target_level = _normalize_target_level(str(goal.get("target_level") or "D1"))
    current_stats = _to_float_map(_as_dict(goal.get("current_stats")))
    identity_fields = _as_dict(goal.get("identity_fields"))

    try:
        sensitivity = compute_sensitivity(
            position_track=position_track,
            current_stats=current_stats,
            identity_fields=identity_fields,
            target_level=target_level,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Sensitivity failed: {exc}") from exc

    computed_at = datetime.now(tz=UTC).isoformat()
    supabase = require_supabase_admin_client()
    supabase.table("player_goals").update(
        {
            "sensitivity_results": sensitivity,
            "sensitivity_computed_at": computed_at,
        }
    ).eq("id", goal_id).eq("user_id", current_user.user_id).execute()

    return {
        "cached": False,
        "computed_at": computed_at,
        "results": sensitivity,
    }


@router.get("/{goal_id}/gap-to-range")
async def get_gap_to_range(goal_id: str, current_user: AuthenticatedUser = Depends(get_current_user)) -> Dict[str, Any]:
    goal = _goal_for_user(goal_id, current_user.user_id)
    position_track = _normalize_position_track(str(goal.get("position_track")))
    target_level = _normalize_target_level(str(goal.get("target_level") or "D1"))
    current_stats = _to_float_map(_as_dict(goal.get("current_stats")))
    stat_config = get_perturbable_stats(position_track)

    supabase = require_supabase_admin_client()
    ranges_response = (
        supabase.table("position_stat_ranges")
        .select("*")
        .eq("position_track", position_track)
        .eq("level", target_level)
        .execute()
    )
    ranges = ranges_response.data or []
    range_by_stat = {str(row.get("stat_name")): row for row in ranges}

    comparisons = []
    for stat_name, value in current_stats.items():
        range_row = range_by_stat.get(stat_name)
        if not range_row:
            continue

        p10 = range_row.get("p10")
        p25 = range_row.get("p25")
        median = range_row.get("median")
        p75 = range_row.get("p75")
        p90 = range_row.get("p90")

        band_status = "within"
        if isinstance(p25, (int, float)) and value < float(p25):
            band_status = "below"
        elif isinstance(p75, (int, float)) and value > float(p75):
            band_status = "above"

        if isinstance(p10, (int, float)) and value < float(p10):
            percentile_zone = "below_p10"
        elif isinstance(p25, (int, float)) and value < float(p25):
            percentile_zone = "p10_to_p25"
        elif isinstance(median, (int, float)) and value < float(median):
            percentile_zone = "p25_to_p50"
        elif isinstance(p75, (int, float)) and value < float(p75):
            percentile_zone = "p50_to_p75"
        elif isinstance(p90, (int, float)) and value < float(p90):
            percentile_zone = "p75_to_p90"
        else:
            percentile_zone = "above_p90"

        config = stat_config.get(stat_name, {})
        comparisons.append(
            {
                "stat_name": stat_name,
                "display_name": config.get("display", stat_name),
                "unit": config.get("unit", ""),
                "current_value": value,
                "p10": p10,
                "p25": p25,
                "median": median,
                "p75": p75,
                "p90": p90,
                "band_status": band_status,
                "percentile_zone": percentile_zone,
                "sample_count": range_row.get("sample_count"),
            }
        )

    return {
        "goal_id": goal_id,
        "position_track": position_track,
        "target_level": target_level,
        "stats": comparisons,
    }
