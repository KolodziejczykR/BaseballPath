"""
Evaluation pipeline orchestration — pure service layer.

This module contains the non-HTTP logic behind the evaluation flow:

  * `run_preview_core` — runs academic + baseball scoring and school matching.
  * `build_teaser` — picks 3 schools at random from the top 10 to tease the
    paid result.
  * `store_pending_evaluation` — inserts the pre-payment preview into
    `pending_evaluations`.
  * `finalize_paid_evaluation` — verifies the Stripe purchase, loads the
    pending row, re-runs matching over the consideration pool, and persists a
    `prediction_runs` row with the authenticated user_id.
  * `list_runs` / `get_run` / `delete_run` / `delete_all_runs` — thin wrappers
    over the `prediction_runs` table scoped to a user.

The router layer translates the custom exceptions raised here into HTTP
responses; nothing in this module should import FastAPI.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from pydantic import BaseModel, Field

from ..clients.supabase import require_supabase_admin_client
from .llm_insight_service import (
    enqueue_deep_school_research,
    should_enqueue_deep_school_research,
)
from .profile_service import get_profile

from backend.evaluation.academic_scoring import compute_academic_score
from backend.evaluation.competitiveness import effective_tier
from backend.evaluation.school_matching import (
    BUDGET_RANGES,
    compute_player_pci,
    match_and_rank_schools,
)
from backend.school_filtering.database.async_queries import AsyncSchoolDataQueries
from backend.utils.position_tracks import (
    is_pitcher_primary_position,
    primary_position_to_track,
)

logger = logging.getLogger(__name__)

DISCLAIMER_TEXT = (
    "This evaluation is based on measurable athletic metrics and academic data only. "
    "Factors that college coaches weigh heavily — including coachability, work ethic, "
    "character, delivery style, baseball IQ, development trajectory, and roster context "
    "— are not captured in this snapshot. Players with unique profiles (sidearm deliveries, "
    "exceptional competitiveness, late physical development) may be undervalued or "
    "overvalued by any metrics-based tool. This is a starting point for your college "
    "baseball search, not the final word."
)

TEASER_POOL_SIZE = 10
TEASER_COUNT = 3


# ---------------------------------------------------------------------------
# Input models (shared between router and service)
# ---------------------------------------------------------------------------


class BaseballMetrics(BaseModel):
    height: int = Field(..., ge=60, le=84)
    weight: int = Field(..., ge=120, le=320)
    primary_position: str
    throwing_hand: str = "R"
    hitting_handedness: Optional[str] = None
    player_region: Optional[str] = None
    graduation_year: Optional[int] = None
    exit_velo_max: Optional[float] = None
    sixty_time: Optional[float] = None
    inf_velo: Optional[float] = None
    of_velo: Optional[float] = None
    c_velo: Optional[float] = None
    pop_time: Optional[float] = None
    fastball_velo_max: Optional[float] = None
    fastball_velo_range: Optional[float] = None
    fastball_spin: Optional[float] = None
    changeup_velo: Optional[float] = None
    changeup_spin: Optional[float] = None
    curveball_velo: Optional[float] = None
    curveball_spin: Optional[float] = None
    slider_velo: Optional[float] = None
    slider_spin: Optional[float] = None


class MLPrediction(BaseModel):
    final_prediction: str
    d1_probability: float
    p4_probability: Optional[float] = None
    confidence: Optional[str] = None
    d1_details: Optional[Dict[str, Any]] = None
    p4_details: Optional[Dict[str, Any]] = None
    player_info: Optional[Dict[str, Any]] = None


class AcademicInput(BaseModel):
    gpa: float = Field(..., ge=0.0, le=4.0)
    sat_score: Optional[int] = Field(None, ge=400, le=1600)
    act_score: Optional[int] = Field(None, ge=1, le=36)
    ap_courses: int = Field(..., ge=0)


class PreferencesInput(BaseModel):
    regions: Optional[List[str]] = None
    max_budget: Optional[str] = None
    ranking_priority: Optional[str] = None


class EvaluateRequest(BaseModel):
    baseball_metrics: BaseballMetrics
    ml_prediction: MLPrediction
    academic_input: AcademicInput
    preferences: PreferencesInput


@dataclass
class CoreEvaluation:
    academic_score: Dict[str, Any]
    player_stats: Dict[str, Any]
    predicted_tier: str
    player_percentile: float
    player_pci: float
    ml_pci: Optional[float]
    is_pitcher: bool
    ranked_schools: List[Dict[str, Any]]

    def baseball_assessment(self, ml: MLPrediction) -> Dict[str, Any]:
        return {
            "predicted_tier": self.predicted_tier,
            "within_tier_percentile": self.player_percentile,
            "player_competitiveness_index": self.player_pci,
            "ml_pci": self.ml_pci,
            "d1_probability": ml.d1_probability,
            "p4_probability": ml.p4_probability,
        }


# ---------------------------------------------------------------------------
# Domain errors (router translates to HTTPException)
# ---------------------------------------------------------------------------


class EvaluationInputError(ValueError):
    """Input validation failed (e.g., missing both SAT and ACT)."""


class PendingEvaluationNotFound(LookupError):
    """Session token does not resolve to a stored pending evaluation."""


class PurchaseNotFound(LookupError):
    """The eval_purchases row referenced by the finalize request is missing."""


class PredictionRunPersistError(RuntimeError):
    """Writing the prediction_runs row failed."""


class LegacyPositionTrackConstraintError(PredictionRunPersistError):
    """prediction_runs.position_track check constraint rejected the insert."""


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------


async def run_preview_core(
    metrics: BaseballMetrics,
    ml: MLPrediction,
    acad: AcademicInput,
    prefs: PreferencesInput,
    *,
    user_state: Optional[str] = None,
    school_limit: int = 15,
    consideration_pool: bool = False,
) -> CoreEvaluation:
    if acad.sat_score is None and acad.act_score is None:
        raise EvaluationInputError("At least one test score (SAT or ACT) is required.")

    is_pitcher_flag = is_pitcher_primary_position(metrics.primary_position)

    academic_score = compute_academic_score(
        gpa=acad.gpa,
        sat_score=acad.sat_score,
        act_score=acad.act_score,
        ap_courses=acad.ap_courses,
    )

    player_stats = metrics.model_dump(exclude_none=True)
    # Demote low-confidence P4/D1 calls so borderline players don't get matched
    # against top-tier schools just because the ML layer used an elite-feature
    # override. effective_tier only ever demotes; a confident call is unchanged.
    predicted_tier = effective_tier(
        ml.final_prediction,
        d1_probability=ml.d1_probability,
        p4_probability=ml.p4_probability,
    )
    player_competitiveness = compute_player_pci(
        player_stats=player_stats,
        predicted_tier=predicted_tier,
        d1_probability=ml.d1_probability,
        p4_probability=ml.p4_probability,
        is_pitcher=is_pitcher_flag,
    )
    player_percentile = float(player_competitiveness.get("within_tier_percentile") or 50.0)
    player_pci = float(player_competitiveness.get("player_pci") or 50.0)

    db = AsyncSchoolDataQueries()
    try:
        all_schools = await db.get_all_schools()
    finally:
        await db.close()

    budget_max: Optional[float] = None
    if prefs.max_budget and prefs.max_budget != "no_preference":
        budget_range = BUDGET_RANGES.get(prefs.max_budget)
        if budget_range:
            budget_max = budget_range[1]

    ranked_schools = match_and_rank_schools(
        schools=all_schools,
        player_stats=player_stats,
        predicted_tier=predicted_tier,
        player_pci=player_pci,
        academic_composite=academic_score["effective"],
        is_pitcher=is_pitcher_flag,
        selected_regions=prefs.regions,
        max_budget=budget_max,
        user_state=user_state,
        limit=school_limit,
        consideration_pool=consideration_pool,
    )

    return CoreEvaluation(
        academic_score=academic_score,
        player_stats=player_stats,
        predicted_tier=predicted_tier,
        player_percentile=player_percentile,
        player_pci=player_pci,
        ml_pci=player_competitiveness.get("ml_pci"),
        is_pitcher=is_pitcher_flag,
        ranked_schools=ranked_schools,
    )


# ---------------------------------------------------------------------------
# Teaser
# ---------------------------------------------------------------------------


def build_teaser(core: CoreEvaluation, rng: Optional[random.Random] = None) -> List[Dict[str, Any]]:
    """
    Pick up to TEASER_COUNT schools at random from the top TEASER_POOL_SIZE
    of the ranked list. Strips the payload to the fields the teaser UI shows.
    """
    pool = core.ranked_schools[:TEASER_POOL_SIZE]
    if not pool:
        return []
    rng = rng or random.Random()
    sample_size = min(TEASER_COUNT, len(pool))
    picked = rng.sample(pool, sample_size)

    teasers: List[Dict[str, Any]] = []
    for school in picked:
        teasers.append(
            {
                "school_name": school.get("school_name"),
                "display_school_name": school.get("display_school_name"),
                "division_group": school.get("division_group"),
                "division_label": school.get("division_label"),
                "baseball_division": school.get("baseball_division"),
                "school_logo_image": school.get("school_logo_image"),
            }
        )
    return teasers


# ---------------------------------------------------------------------------
# Pending evaluation storage
# ---------------------------------------------------------------------------


def store_pending_evaluation(
    *,
    session_token: str,
    payload: EvaluateRequest,
    core: CoreEvaluation,
    user_id: Optional[str] = None,
) -> None:
    preview_results = {
        "schools": core.ranked_schools,
        "academic_score": core.academic_score,
        "baseball_assessment": core.baseball_assessment(payload.ml_prediction),
    }
    supabase = require_supabase_admin_client()
    insert_data = {
        "session_token": session_token,
        "user_id": user_id,
        "baseball_metrics": payload.baseball_metrics.model_dump(),
        "ml_prediction": payload.ml_prediction.model_dump(),
        "academic_input": payload.academic_input.model_dump(),
        "preferences": payload.preferences.model_dump(),
        "preview_results": preview_results,
    }
    result = supabase.table("pending_evaluations").insert(insert_data).execute()
    if not result.data:
        raise PredictionRunPersistError("Failed to store pending evaluation")


def create_pending_session_token() -> str:
    return str(uuid4())


# ---------------------------------------------------------------------------
# Finalize
# ---------------------------------------------------------------------------


def _is_prediction_runs_position_track_constraint_error(exc: Exception) -> bool:
    return "prediction_runs_position_track_check" in str(exc)


def _insert_prediction_run(supabase: Any, insert_payload: Dict[str, Any]):
    try:
        return supabase.table("prediction_runs").insert(insert_payload).execute()
    except Exception as exc:
        if _is_prediction_runs_position_track_constraint_error(exc):
            logger.exception(
                "prediction_runs.position_track constraint rejected value %r; "
                "apply migration 20260327_prediction_runs_add_catcher.sql",
                insert_payload.get("position_track"),
            )
            raise LegacyPositionTrackConstraintError(
                "Database schema rejected position_track. "
                "Apply migration 20260327_prediction_runs_add_catcher.sql."
            ) from exc
        raise


async def finalize_paid_evaluation(
    *,
    user_id: str,
    user_email: Optional[str],
    session_token: str,
    purchase_id: str,
) -> Dict[str, Any]:
    """
    Verify a paid purchase, load the matching pending evaluation, re-run the
    matching pipeline over a wider consideration pool, persist a prediction_runs
    row with user_id, and enqueue deep research.

    Raises PurchaseNotFound / PendingEvaluationNotFound / PredictionRunPersistError.
    """
    supabase = require_supabase_admin_client()

    purchase_result = (
        supabase.table("eval_purchases")
        .select("*")
        .eq("id", purchase_id)
        .execute()
    )
    if not purchase_result.data:
        raise PurchaseNotFound("Purchase not found")
    purchase = purchase_result.data[0]
    if purchase.get("user_id") and purchase["user_id"] != user_id:
        raise PurchaseNotFound("Purchase belongs to a different user")

    pending_result = (
        supabase.table("pending_evaluations")
        .select("*")
        .eq("session_token", session_token)
        .execute()
    )
    if not pending_result.data:
        raise PendingEvaluationNotFound("Pending evaluation not found or expired")
    pending = pending_result.data[0]

    preview = pending["preview_results"]
    academic_score = preview["academic_score"]
    baseball_assessment = preview["baseball_assessment"]
    player_stats = pending["baseball_metrics"]
    ml_data = pending["ml_prediction"]
    prefs_data = pending["preferences"]
    acad_data = pending["academic_input"]

    core = await run_preview_core(
        BaseballMetrics(**player_stats),
        MLPrediction(**ml_data),
        AcademicInput(**acad_data),
        PreferencesInput(**prefs_data),
        school_limit=50,
        consideration_pool=True,
    )
    consideration_schools = core.ranked_schools

    profile = get_profile(user_id, user_email)
    profile_name = profile.get("full_name", "")
    user_state = profile.get("state", "")

    insert_payload: Dict[str, Any] = {
        "user_id": user_id,
        "purchase_id": purchase_id,
        "position_track": primary_position_to_track(player_stats.get("primary_position", "")),
        "identity_input": {
            "name": profile_name,
            "state": user_state,
            "graduating_class": player_stats.get("graduation_year"),
        },
        "stats_input": player_stats,
        "preferences_input": {
            "regions": prefs_data.get("regions"),
            "max_budget": prefs_data.get("max_budget"),
            "academic_input": acad_data,
        },
        "prediction_response": ml_data,
        "preferences_response": {
            "schools": [],
            "academic_score": academic_score,
            "baseball_assessment": baseball_assessment,
        },
        "top_schools_snapshot": [],
        "llm_reasoning_status": (
            "processing" if should_enqueue_deep_school_research(consideration_schools) else "skipped"
        ),
        "llm_job_id": None,
    }

    response = _insert_prediction_run(supabase, insert_payload)
    if not response.data:
        raise PredictionRunPersistError("Failed to persist evaluation run")
    run_id = response.data[0].get("id", "")

    supabase.table("eval_purchases").update(
        {"eval_run_id": run_id, "updated_at": "now()"}
    ).eq("id", purchase_id).execute()

    llm_status, llm_job_id = enqueue_deep_school_research(
        run_id=run_id,
        schools=consideration_schools,
        player_stats=player_stats,
        baseball_assessment=baseball_assessment,
        academic_score=academic_score,
        final_limit=15,
        ranking_priority=prefs_data.get("ranking_priority"),
    )
    supabase.table("prediction_runs").update(
        {
            "llm_reasoning_status": llm_status,
            "llm_job_id": llm_job_id,
        }
    ).eq("id", run_id).execute()

    return {
        "run_id": run_id,
        "disclaimer": DISCLAIMER_TEXT,
        "baseball_assessment": {
            "predicted_tier": baseball_assessment["predicted_tier"],
            "within_tier_percentile": baseball_assessment["within_tier_percentile"],
            "player_competitiveness_index": baseball_assessment.get("player_competitiveness_index"),
            "ml_pci": baseball_assessment.get("ml_pci"),
            "d1_probability": baseball_assessment.get("d1_probability"),
            "p4_probability": baseball_assessment.get("p4_probability"),
            "confidence": ml_data.get("confidence"),
        },
        "academic_assessment": academic_score,
        "schools": [],
        "llm_reasoning_status": llm_status,
    }


# ---------------------------------------------------------------------------
# Public result polling (token-gated, no auth)
# ---------------------------------------------------------------------------


def _run_to_public_result(run_row: Dict[str, Any]) -> Dict[str, Any]:
    preferences_response = run_row.get("preferences_response") or {}
    return {
        "run_id": run_row.get("id", ""),
        "disclaimer": DISCLAIMER_TEXT,
        "baseball_assessment": preferences_response.get("baseball_assessment"),
        "academic_assessment": preferences_response.get("academic_score"),
        "schools": preferences_response.get("schools") or [],
        "llm_reasoning_status": run_row.get("llm_reasoning_status") or "skipped",
    }


def get_public_result(run_id: str, purchase_id: str, session_token: str) -> Dict[str, Any]:
    """
    Token-gated public result poll. Verifies the session_token + purchase_id
    match a completed prediction run and returns the public view.

    Raises PendingEvaluationNotFound / PurchaseNotFound.
    """
    supabase = require_supabase_admin_client()

    pending_result = (
        supabase.table("pending_evaluations")
        .select("id")
        .eq("session_token", session_token)
        .limit(1)
        .execute()
    )
    if not pending_result.data:
        raise PendingEvaluationNotFound("Pending evaluation not found or expired")

    purchase_result = (
        supabase.table("eval_purchases")
        .select("id, status, eval_run_id")
        .eq("id", purchase_id)
        .limit(1)
        .execute()
    )
    if not purchase_result.data:
        raise PurchaseNotFound("Purchase not found")
    purchase = purchase_result.data[0]
    if purchase.get("status") != "completed" or purchase.get("eval_run_id") != run_id:
        raise PurchaseNotFound("Evaluation result is not available for this purchase")

    run_result = (
        supabase.table("prediction_runs")
        .select("*")
        .eq("id", run_id)
        .limit(1)
        .execute()
    )
    if not run_result.data:
        raise PendingEvaluationNotFound("Evaluation run not found")

    return _run_to_public_result(run_result.data[0])


# ---------------------------------------------------------------------------
# Per-user prediction_runs CRUD (for the authenticated runs list)
# ---------------------------------------------------------------------------


def list_runs(user_id: str, *, limit: int, offset: int) -> Dict[str, Any]:
    supabase = require_supabase_admin_client()
    end_index = offset + limit - 1
    response = (
        supabase.table("prediction_runs")
        .select("*", count="exact")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .range(offset, end_index)
        .execute()
    )
    return {
        "items": response.data or [],
        "limit": limit,
        "offset": offset,
        "total": getattr(response, "count", None),
    }


def get_run(user_id: str, run_id: str) -> Optional[Dict[str, Any]]:
    supabase = require_supabase_admin_client()
    response = (
        supabase.table("prediction_runs")
        .select("*")
        .eq("id", run_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return response.data[0]


def delete_run(user_id: str, run_id: str) -> bool:
    supabase = require_supabase_admin_client()
    existing = (
        supabase.table("prediction_runs")
        .select("id")
        .eq("id", run_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        return False
    supabase.table("prediction_runs").delete().eq("id", run_id).eq("user_id", user_id).execute()
    return True


def delete_all_runs(user_id: str) -> int:
    supabase = require_supabase_admin_client()
    count_response = (
        supabase.table("prediction_runs")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    deleted_count = int(getattr(count_response, "count", None) or 0)
    if deleted_count == 0:
        return 0
    supabase.table("prediction_runs").delete().eq("user_id", user_id).execute()
    return deleted_count
