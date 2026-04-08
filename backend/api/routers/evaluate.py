"""
V2 Evaluation endpoint — 3-step evaluation flow with baseball + academic matching.

Supports two flows:
  - Preview (no auth required): ML + academic scoring + school matching, stored as pending
  - Finalize (auth + payment required): LLM insights + persistence to prediction_runs
  - Claim: links a pending evaluation to a newly created user account
  - Legacy /run endpoint kept for backward compatibility
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..clients.supabase import require_supabase_admin_client
from ..deps.auth import AuthenticatedUser, get_current_user, get_optional_user
from ..services.plan_service import (
    enforce_evaluation_quota,
    get_effective_plan,
    get_profile,
    increment_usage,
    remaining_evaluations,
)
from ..services.pricing_service import get_eval_price

from backend.evaluation.academic_scoring import compute_academic_score
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
from backend.utils.school_group_constants import POWER_4_D1, NON_P4_D1, NON_D1

logger = logging.getLogger(__name__)

router = APIRouter()

# LLM integration (optional — uses existing OpenAI setup)
try:
    from openai import OpenAI
    _openai_client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        max_retries=0,
    )
    _llm_model = os.getenv("OPENAI_SUMMARY_MODEL", "gpt-5.4-nano")
except Exception:
    _openai_client = None
    _llm_model = None

try:
    from backend.llm.tasks import generate_deep_school_research
except Exception:
    generate_deep_school_research = None


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class BaseballMetrics(BaseModel):
    height: int = Field(..., ge=60, le=84)
    weight: int = Field(..., ge=120, le=320)
    primary_position: str
    throwing_hand: str = "R"
    hitting_handedness: Optional[str] = None
    player_region: Optional[str] = None
    graduation_year: Optional[int] = None
    # Hitter fields
    exit_velo_max: Optional[float] = None
    sixty_time: Optional[float] = None
    inf_velo: Optional[float] = None
    of_velo: Optional[float] = None
    c_velo: Optional[float] = None
    pop_time: Optional[float] = None
    # Pitcher fields
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
    regions: Optional[List[str]] = None  # None = all regions
    max_budget: Optional[str] = None  # Budget key or "no_preference"


class EvaluateRequest(BaseModel):
    baseball_metrics: BaseballMetrics
    ml_prediction: MLPrediction
    academic_input: AcademicInput
    preferences: PreferencesInput


class ClaimRequest(BaseModel):
    session_token: str
    purchase_id: Optional[str] = None


class FinalizeRequest(BaseModel):
    session_token: str
    purchase_id: str


# ---------------------------------------------------------------------------
# LLM insights
# ---------------------------------------------------------------------------

DISCLAIMER_TEXT = (
    "This evaluation is based on measurable athletic metrics and academic data only. "
    "Factors that college coaches weigh heavily — including coachability, work ethic, "
    "character, delivery style, baseball IQ, development trajectory, and roster context "
    "— are not captured in this snapshot. Players with unique profiles (sidearm deliveries, "
    "exceptional competitiveness, late physical development) may be undervalued or "
    "overvalued by any metrics-based tool. This is a starting point for your college "
    "baseball search, not the final word."
)


def _build_llm_insights_prompt(
    schools: List[Dict[str, Any]],
    player_stats: Dict[str, Any],
    predicted_tier: str,
    academic_score: Dict[str, Any],
    is_pitcher: bool,
) -> str:
    """Build a batched LLM prompt for all schools."""
    # Sanitize player stats for prompt (remove internal fields)
    safe_stats = {k: v for k, v in player_stats.items() if v is not None}

    schools_for_prompt = []
    for s in schools:
        schools_for_prompt.append({
            "rank": s["rank"],
            "school_name": s["school_name"],
            "conference": s.get("conference"),
            "division_group": s["division_group"],
            "state": s["location"]["state"],
            "baseball_fit": s["baseball_fit"],
            "academic_fit": s["academic_fit"],
            "niche_academic_grade": s.get("niche_academic_grade"),
            "estimated_annual_cost": s.get("estimated_annual_cost"),
            "metric_comparisons": s.get("metric_comparisons", []),
        })

    return (
        "You are a college baseball recruiting analyst. Generate insights for each school "
        "in the list below based on the player's profile and how they compare to the school's tier.\n\n"
        "RULES:\n"
        "- Do NOT expose proprietary scores (no 'your academic score is 7.2' or 'ML confidence 62%')\n"
        "- Use natural language only: reference the player's actual metrics vs division averages\n"
        "- Each school gets:\n"
        "  1. fit_summary: 2-3 sentences explaining why this school is a reach/fit/safety for this player, "
        "referencing specific metrics from metric_comparisons\n"
        "  2. school_description: 1-2 sentences about what the school/program is known for\n"
        "- Respond in JSON only, no preamble or explanation.\n\n"
        "JSON schema:\n"
        '{"schools": [{"school_name": "string", "fit_summary": "string", "school_description": "string"}]}\n\n'
        f"PLAYER PROFILE:\n"
        f"Position: {player_stats.get('primary_position', 'Unknown')}\n"
        f"Predicted Tier: {predicted_tier}\n"
        f"Player Type: {'Pitcher' if is_pitcher else 'Position Player'}\n"
        f"Stats: {json.dumps(safe_stats)}\n\n"
        f"SCHOOLS:\n{json.dumps(schools_for_prompt)}\n"
    )


def _call_llm_insights(
    schools: List[Dict[str, Any]],
    player_stats: Dict[str, Any],
    predicted_tier: str,
    academic_score: Dict[str, Any],
    is_pitcher: bool,
) -> Dict[str, Dict[str, str]]:
    """
    Call LLM for batched school insights. Returns {school_name: {fit_summary, school_description}}.
    """
    if _openai_client is None:
        logger.warning("OpenAI client not available, skipping LLM insights")
        return {}

    prompt = _build_llm_insights_prompt(
        schools, player_stats, predicted_tier, academic_score, is_pitcher
    )

    try:
        response = _openai_client.chat.completions.create(
            model=_llm_model,
            messages=[
                {"role": "system", "content": "You are a concise college baseball recruiting analyst. Respond in JSON only."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=4096,
        )
        content = response.choices[0].message.content.strip()

        # Parse JSON
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1:
                data = json.loads(content[start:end + 1])
            else:
                return {}

        result = {}
        for item in data.get("schools", []):
            name = item.get("school_name")
            if name:
                result[name] = {
                    "fit_summary": item.get("fit_summary", ""),
                    "school_description": item.get("school_description", ""),
                }
        return result

    except Exception as e:
        logger.error(f"LLM insights call failed: {e}")
        return {}


def _apply_basic_school_insights(
    schools: List[Dict[str, Any]],
    player_stats: Dict[str, Any],
    baseball_assessment: Dict[str, Any],
    academic_score: Dict[str, Any],
    is_pitcher: bool,
) -> List[Dict[str, Any]]:
    """
    Apply only the fast batched school summaries.
    Deep roster research runs in a background job after the run is persisted.
    """
    if not schools:
        return schools

    working = [dict(school) for school in schools]

    llm_insights = _call_llm_insights(
        working,
        player_stats,
        baseball_assessment["predicted_tier"],
        academic_score,
        is_pitcher,
    )
    for school in working:
        insights = llm_insights.get(school["school_name"], {})
        school["fit_summary"] = insights.get("fit_summary", "")
        school["school_description"] = insights.get("school_description", "")

    return working


def _should_enqueue_deep_school_research(schools: List[Dict[str, Any]]) -> bool:
    return bool(_openai_client is not None and generate_deep_school_research is not None and schools)


def _attach_roster_urls(schools: List[Dict[str, Any]]) -> None:
    """Look up baseball_roster_url from school_data_general and attach as roster_url."""
    supabase = require_supabase_admin_client()
    school_names = [s.get("school_name", "") for s in schools if s.get("school_name")]
    if not school_names:
        return
    try:
        resp = (
            supabase.table("school_data_general")
            .select("school_name, baseball_roster_url")
            .in_("school_name", school_names)
            .execute()
        )
        url_map = {row["school_name"]: row["baseball_roster_url"] for row in (resp.data or []) if row.get("baseball_roster_url")}
        for school in schools:
            name = school.get("school_name", "")
            if name in url_map:
                school["roster_url"] = url_map[name]
    except Exception as exc:
        logger.warning("Failed to look up roster URLs: %s", exc)


def _enqueue_deep_school_research(
    *,
    run_id: str,
    schools: List[Dict[str, Any]],
    player_stats: Dict[str, Any],
    baseball_assessment: Dict[str, Any],
    academic_score: Dict[str, Any],
    final_limit: Optional[int] = None,
) -> tuple[str, Optional[str]]:
    if not _should_enqueue_deep_school_research(schools):
        return "skipped", None

    _attach_roster_urls(schools)

    try:
        payload: Dict[str, Any] = {
            "run_id": run_id,
            "schools": schools,
            "player_stats": player_stats,
            "baseball_assessment": baseball_assessment,
            "academic_score": academic_score,
        }
        if final_limit is not None:
            payload["final_limit"] = final_limit
        job = generate_deep_school_research.delay(payload)
        return "processing", getattr(job, "id", None)
    except Exception as exc:
        logger.warning("Failed to enqueue deep school research for run %s: %s", run_id, exc)
        return "failed", None


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


def _is_pitcher(position: str) -> bool:
    return is_pitcher_primary_position(position)


def _position_endpoint(position: str) -> str:
    return primary_position_to_track(position)


def _is_prediction_runs_position_track_constraint_error(exc: Exception) -> bool:
    """
    Detect legacy prediction_runs check-constraint failures that do not permit
    `position_track='catcher'`.
    """
    message = str(exc)
    return "prediction_runs_position_track_check" in message


def _insert_prediction_run(
    supabase: Any,
    insert_payload: Dict[str, Any],
):
    """
    Insert into prediction_runs and convert common schema failures into a clean
    API error response.
    """
    try:
        return supabase.table("prediction_runs").insert(insert_payload).execute()
    except Exception as exc:
        if _is_prediction_runs_position_track_constraint_error(exc):
            logger.exception(
                "prediction_runs.position_track constraint rejected value %r; "
                "apply migration 20260327_prediction_runs_add_catcher.sql",
                insert_payload.get("position_track"),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "Database schema rejected position_track. "
                    "Apply migration 20260327_prediction_runs_add_catcher.sql."
                ),
            ) from exc
        raise


# ---------------------------------------------------------------------------
# Shared evaluation logic (used by both preview and legacy run)
# ---------------------------------------------------------------------------

async def _run_core_evaluation(
    metrics: BaseballMetrics,
    ml: MLPrediction,
    acad: AcademicInput,
    prefs: PreferencesInput,
    user_state: Optional[str] = None,
    school_limit: int = 15,
    consideration_pool: bool = False,
) -> Dict[str, Any]:
    """Run academic scoring, baseball assessment, and school matching (no LLM)."""
    if acad.sat_score is None and acad.act_score is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one test score (SAT or ACT) is required.",
        )

    is_pitcher_flag = _is_pitcher(metrics.primary_position)

    academic_score = compute_academic_score(
        gpa=acad.gpa,
        sat_score=acad.sat_score,
        act_score=acad.act_score,
        ap_courses=acad.ap_courses,
    )

    player_stats = metrics.model_dump(exclude_none=True)
    predicted_tier = ml.final_prediction
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

    budget_max = None
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

    return {
        "academic_score": academic_score,
        "player_stats": player_stats,
        "predicted_tier": predicted_tier,
        "player_percentile": player_percentile,
        "player_pci": player_pci,
        "ml_pci": player_competitiveness.get("ml_pci"),
        "benchmark_pci": player_competitiveness.get("benchmark_pci"),
        "is_pitcher": is_pitcher_flag,
        "ranked_schools": ranked_schools,
    }


# ---------------------------------------------------------------------------
# POST /evaluate/preview — no auth required, no LLM
# ---------------------------------------------------------------------------

@router.post("/preview")
async def preview_evaluation(
    payload: EvaluateRequest,
    current_user: Optional[AuthenticatedUser] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """
    Run the evaluation pipeline without LLM insights.
    Stores results in pending_evaluations and returns a session_token.
    No results data is returned — user must pay to see results.
    """
    core = await _run_core_evaluation(
        payload.baseball_metrics,
        payload.ml_prediction,
        payload.academic_input,
        payload.preferences,
    )

    session_token = str(uuid4())

    # Build preview_results for storage (everything except LLM)
    preview_results = {
        "schools": core["ranked_schools"],
        "academic_score": core["academic_score"],
        "baseball_assessment": {
            "predicted_tier": core["predicted_tier"],
            "within_tier_percentile": core["player_percentile"],
            "player_competitiveness_index": core["player_pci"],
            "ml_pci": core.get("ml_pci"),
            "benchmark_pci": core.get("benchmark_pci"),
            "d1_probability": payload.ml_prediction.d1_probability,
            "p4_probability": payload.ml_prediction.p4_probability,
        },
    }

    supabase = require_supabase_admin_client()
    insert_data = {
        "session_token": session_token,
        "user_id": current_user.user_id if current_user else None,
        "baseball_metrics": payload.baseball_metrics.model_dump(),
        "ml_prediction": payload.ml_prediction.model_dump(),
        "academic_input": payload.academic_input.model_dump(),
        "preferences": payload.preferences.model_dump(),
        "preview_results": preview_results,
    }

    result = supabase.table("pending_evaluations").insert(insert_data).execute()
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store pending evaluation",
        )

    # Determine price if user is authenticated
    price_cents = None
    is_first_eval = None
    if current_user:
        pricing = get_eval_price(current_user.user_id)
        price_cents = pricing["price_cents"]
        is_first_eval = pricing["is_first_eval"]

    return {
        "session_token": session_token,
        "price_cents": price_cents,
        "is_first_eval": is_first_eval,
    }


# ---------------------------------------------------------------------------
# POST /evaluate/claim — link pending eval to authenticated user
# ---------------------------------------------------------------------------

@router.post("/claim")
async def claim_evaluation(
    payload: ClaimRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Link a pending evaluation to the authenticated user (called after signup)."""
    supabase = require_supabase_admin_client()

    # Verify the pending evaluation exists and isn't already claimed by another user
    result = (
        supabase.table("pending_evaluations")
        .select("id, user_id")
        .eq("session_token", payload.session_token)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending evaluation not found or expired",
        )

    pending = result.data[0]
    if pending["user_id"] and pending["user_id"] != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This evaluation belongs to another user",
        )

    # Update user_id on pending_evaluations
    supabase.table("pending_evaluations").update(
        {"user_id": current_user.user_id}
    ).eq("session_token", payload.session_token).execute()

    # If purchase_id provided, also claim eval_purchases and prediction_runs
    if payload.purchase_id:
        # Claim the purchase
        supabase.table("eval_purchases").update(
            {"user_id": current_user.user_id}
        ).eq("id", payload.purchase_id).is_("user_id", "null").execute()

        # Claim the prediction run linked to this purchase
        supabase.table("prediction_runs").update(
            {"user_id": current_user.user_id}
        ).eq("purchase_id", payload.purchase_id).is_("user_id", "null").execute()

    # Return pricing for this user
    pricing = get_eval_price(current_user.user_id)

    return {
        "success": True,
        "price_cents": pricing["price_cents"],
        "is_first_eval": pricing["is_first_eval"],
    }


# ---------------------------------------------------------------------------
# POST /evaluate/finalize — payment required (auth optional), runs LLM
# ---------------------------------------------------------------------------

@router.post("/finalize")
async def finalize_evaluation(
    payload: FinalizeRequest,
    current_user: Optional[AuthenticatedUser] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """
    Finalize a paid evaluation: verify payment, run LLM insights, persist to prediction_runs.
    Auth is optional — unauthenticated users get results but must create an account to save them.
    """
    supabase = require_supabase_admin_client()

    # --- Verify purchase is completed (lookup by ID only, no user_id filter) ---
    purchase_result = (
        supabase.table("eval_purchases")
        .select("*")
        .eq("id", payload.purchase_id)
        .execute()
    )

    if not purchase_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase not found",
        )

    purchase = purchase_result.data[0]

    if purchase["status"] != "completed":
        # Fallback: check Stripe directly in case webhook hasn't arrived yet
        try:
            import stripe
            stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
            if purchase.get("stripe_checkout_session_id"):
                session = stripe.checkout.Session.retrieve(
                    purchase["stripe_checkout_session_id"]
                )
                if session.payment_status == "paid":
                    supabase.table("eval_purchases").update(
                        {"status": "completed", "updated_at": "now()"}
                    ).eq("id", payload.purchase_id).execute()
                    purchase["status"] = "completed"
        except Exception as e:
            logger.warning(f"Stripe verification fallback failed: {e}")

        if purchase["status"] != "completed":
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Payment has not been confirmed yet",
            )

    # --- Load pending evaluation (by session_token only) ---
    pending_result = (
        supabase.table("pending_evaluations")
        .select("*")
        .eq("session_token", payload.session_token)
        .execute()
    )

    if not pending_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending evaluation not found or expired",
        )

    pending = pending_result.data[0]
    preview = pending["preview_results"]
    academic_score = preview["academic_score"]
    baseball_assessment = preview["baseball_assessment"]
    player_stats = pending["baseball_metrics"]
    ml_data = pending["ml_prediction"]
    prefs_data = pending["preferences"]
    acad_data = pending["academic_input"]

    # --- Build the broad consideration pool for research-first selection ---
    # Re-run matching with wider cutoffs so roster research can promote/demote
    # schools that pure metrics alone would have cut or missed.
    core = await _run_core_evaluation(
        BaseballMetrics(**player_stats),
        MLPrediction(**ml_data),
        AcademicInput(**acad_data),
        PreferencesInput(**prefs_data),
        school_limit=30,
        consideration_pool=True,
    )
    consideration_schools = core["ranked_schools"]

    # --- Persist to prediction_runs ---
    user_id = current_user.user_id if current_user else None
    profile_name = ""
    user_state = ""
    if current_user:
        profile = get_profile(current_user.user_id, current_user.email)
        profile_name = profile.get("full_name", "")
        user_state = profile.get("state", "")

    insert_payload: Dict[str, Any] = {
        "purchase_id": payload.purchase_id,
        "position_track": _position_endpoint(player_stats.get("primary_position", "")),
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
        "llm_reasoning_status": "processing" if _should_enqueue_deep_school_research(consideration_schools) else "skipped",
        "llm_job_id": None,
    }
    if user_id:
        insert_payload["user_id"] = user_id

    response = _insert_prediction_run(supabase, insert_payload)
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist evaluation run",
        )
    run_id = response.data[0].get("id", "")

    # Link purchase to run
    supabase.table("eval_purchases").update(
        {"eval_run_id": run_id, "updated_at": "now()"}
    ).eq("id", payload.purchase_id).execute()

    llm_status, llm_job_id = _enqueue_deep_school_research(
        run_id=run_id,
        schools=consideration_schools,
        player_stats=player_stats,
        baseball_assessment=baseball_assessment,
        academic_score=academic_score,
        final_limit=15,
    )
    supabase.table("prediction_runs").update(
        {
            "llm_reasoning_status": llm_status,
            "llm_job_id": llm_job_id,
        }
    ).eq("id", run_id).execute()

    # Don't delete pending_evaluations yet — keep until user claims or it expires
    # This allows the claim endpoint to link it to a user account later

    # Increment usage tracking if authenticated
    if current_user:
        increment_usage(current_user.user_id, evaluation_increment=1)

    return {
        "run_id": run_id,
        "disclaimer": DISCLAIMER_TEXT,
        "baseball_assessment": {
            "predicted_tier": baseball_assessment["predicted_tier"],
            "within_tier_percentile": baseball_assessment["within_tier_percentile"],
            "player_competitiveness_index": baseball_assessment.get("player_competitiveness_index"),
            "ml_pci": baseball_assessment.get("ml_pci"),
            "benchmark_pci": baseball_assessment.get("benchmark_pci"),
            "d1_probability": baseball_assessment.get("d1_probability"),
            "p4_probability": baseball_assessment.get("p4_probability"),
            "confidence": ml_data.get("confidence"),
        },
        "academic_assessment": academic_score,
        "schools": [],
        "llm_reasoning_status": llm_status,
    }


@router.get("/result")
async def get_public_finalized_result(
    run_id: str = Query(...),
    purchase_id: str = Query(...),
    session_token: str = Query(...),
) -> Dict[str, Any]:
    """
    Poll a finalized evaluation without authentication.
    Access is gated by the original session_token plus purchase_id.
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending evaluation not found or expired",
        )

    purchase_result = (
        supabase.table("eval_purchases")
        .select("id, status, eval_run_id")
        .eq("id", purchase_id)
        .limit(1)
        .execute()
    )
    if not purchase_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase not found",
        )
    purchase = purchase_result.data[0]
    if purchase.get("status") != "completed" or purchase.get("eval_run_id") != run_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evaluation result is not available for this purchase",
        )

    run_result = (
        supabase.table("prediction_runs")
        .select("*")
        .eq("id", run_id)
        .limit(1)
        .execute()
    )
    if not run_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation run not found",
        )

    return _run_to_public_result(run_result.data[0])


# ---------------------------------------------------------------------------
# Legacy: POST /evaluate/run — kept for backward compatibility
# ---------------------------------------------------------------------------

@router.post("/run")
async def run_evaluation(
    payload: EvaluateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Run the full V2 evaluation pipeline (legacy — kept for backward compatibility)."""

    # --- Auth & quota ---
    profile = get_profile(current_user.user_id, current_user.email)
    effective_plan = get_effective_plan(current_user.user_id)
    usage_before = enforce_evaluation_quota(current_user.user_id, effective_plan)

    user_state = profile.get("state")

    # Build the broad consideration pool for research-first selection
    core = await _run_core_evaluation(
        payload.baseball_metrics,
        payload.ml_prediction,
        payload.academic_input,
        payload.preferences,
        user_state=user_state,
        school_limit=30,
        consideration_pool=True,
    )

    consideration_schools = core["ranked_schools"]
    academic_score = core["academic_score"]
    player_stats = core["player_stats"]
    predicted_tier = core["predicted_tier"]
    player_percentile = core["player_percentile"]
    player_pci = core.get("player_pci")
    ml_pci = core.get("ml_pci")
    benchmark_pci = core.get("benchmark_pci")
    metrics = payload.baseball_metrics
    ml = payload.ml_prediction
    acad = payload.academic_input
    prefs = payload.preferences

    # --- Persist ---
    supabase = require_supabase_admin_client()

    baseball_assessment = {
        "predicted_tier": predicted_tier,
        "within_tier_percentile": player_percentile,
        "player_competitiveness_index": player_pci,
        "ml_pci": ml_pci,
        "benchmark_pci": benchmark_pci,
        "d1_probability": ml.d1_probability,
        "p4_probability": ml.p4_probability,
    }
    insert_payload = {
        "user_id": current_user.user_id,
        "position_track": _position_endpoint(metrics.primary_position),
        "identity_input": {
            "name": profile.get("full_name", ""),
            "state": user_state or "",
            "graduating_class": metrics.graduation_year,
        },
        "stats_input": player_stats,
        "preferences_input": {
            "regions": prefs.regions,
            "max_budget": prefs.max_budget,
            "academic_input": acad.model_dump(),
        },
        "prediction_response": ml.model_dump(),
        "preferences_response": {
            "schools": [],
            "academic_score": academic_score,
            "baseball_assessment": baseball_assessment,
        },
        "top_schools_snapshot": [],
        "llm_reasoning_status": "processing" if _should_enqueue_deep_school_research(consideration_schools) else "skipped",
        "llm_job_id": None,
    }

    response = _insert_prediction_run(supabase, insert_payload)
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist evaluation run",
        )
    run_id = response.data[0].get("id", "")

    llm_status, llm_job_id = _enqueue_deep_school_research(
        run_id=run_id,
        schools=consideration_schools,
        player_stats=player_stats,
        baseball_assessment=baseball_assessment,
        academic_score=academic_score,
        final_limit=15,
    )
    supabase.table("prediction_runs").update(
        {
            "llm_reasoning_status": llm_status,
            "llm_job_id": llm_job_id,
        }
    ).eq("id", run_id).execute()

    usage_after = increment_usage(current_user.user_id, evaluation_increment=1)

    return {
        "run_id": run_id,
        "disclaimer": DISCLAIMER_TEXT,
        "baseball_assessment": {
            "predicted_tier": predicted_tier,
            "within_tier_percentile": player_percentile,
            "player_competitiveness_index": player_pci,
            "ml_pci": ml_pci,
            "benchmark_pci": benchmark_pci,
            "d1_probability": ml.d1_probability,
            "p4_probability": ml.p4_probability,
            "confidence": ml.confidence,
        },
        "academic_assessment": academic_score,
        "schools": [],
        "llm_reasoning_status": llm_status,
        "entitlement": {
            "plan_tier": effective_plan.plan_tier,
            "monthly_eval_limit": effective_plan.monthly_eval_limit,
            "remaining_evals": remaining_evaluations(effective_plan, usage_after),
        },
    }
