"""
Evaluation HTTP endpoints.

Three flows live here:
  * POST /evaluations/preview — anonymous, runs the evaluation and stores a
    pending row. Returns a session_token and 3 randomly-selected teaser
    schools from the top 10.
  * POST /evaluations/finalize — authenticated. Requires a purchase_id and
    session_token, runs the full consideration-pool pipeline, persists a
    prediction_runs row, and enqueues deep research.
  * GET /evaluations/result — token-gated public poll used by the results
    page before the user is logged in.

Plus the authenticated list/get/delete endpoints for a user's runs.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..deps.auth import AuthenticatedUser, get_current_user, get_optional_user
from ..services import evaluation_service
from ..services.evaluation_service import (
    DISCLAIMER_TEXT,
    EvaluateRequest,
    EvaluationInputError,
    LegacyPositionTrackConstraintError,
    PendingEvaluationNotFound,
    PredictionRunPersistError,
    PurchaseNotFound,
)
from ..services.pricing_service import get_eval_price

router = APIRouter()


class FinalizeRequest(BaseModel):
    session_token: str
    purchase_id: str


# ---------------------------------------------------------------------------
# POST /evaluations/preview — anonymous
# ---------------------------------------------------------------------------


@router.post("/preview")
async def preview_evaluation(
    payload: EvaluateRequest,
    current_user: Optional[AuthenticatedUser] = Depends(get_optional_user),
) -> Dict[str, Any]:
    try:
        core = await evaluation_service.run_preview_core(
            payload.baseball_metrics,
            payload.ml_prediction,
            payload.academic_input,
            payload.preferences,
        )
    except EvaluationInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    session_token = evaluation_service.create_pending_session_token()
    try:
        evaluation_service.store_pending_evaluation(
            session_token=session_token,
            payload=payload,
            core=core,
            user_id=current_user.user_id if current_user else None,
        )
    except PredictionRunPersistError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc

    teaser_schools = evaluation_service.build_teaser(core)

    price_cents: Optional[int] = None
    is_first_eval: Optional[bool] = None
    if current_user:
        pricing = get_eval_price(current_user.user_id)
        price_cents = pricing["price_cents"]
        is_first_eval = pricing["is_first_eval"]

    return {
        "session_token": session_token,
        "teaser_schools": teaser_schools,
        "price_cents": price_cents,
        "is_first_eval": is_first_eval,
    }


# ---------------------------------------------------------------------------
# POST /evaluations/finalize — authenticated
# ---------------------------------------------------------------------------


@router.post("/finalize")
async def finalize_evaluation(
    payload: FinalizeRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        return await evaluation_service.finalize_paid_evaluation(
            user_id=current_user.user_id,
            user_email=current_user.email,
            session_token=payload.session_token,
            purchase_id=payload.purchase_id,
        )
    except PurchaseNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PendingEvaluationNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except LegacyPositionTrackConstraintError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc
    except PredictionRunPersistError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc


# ---------------------------------------------------------------------------
# GET /evaluations/result — token-gated public poll
# ---------------------------------------------------------------------------


@router.get("/result")
async def get_public_finalized_result(
    run_id: str = Query(...),
    purchase_id: str = Query(...),
    session_token: str = Query(...),
) -> Dict[str, Any]:
    try:
        return evaluation_service.get_public_result(
            run_id=run_id, purchase_id=purchase_id, session_token=session_token
        )
    except PendingEvaluationNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PurchaseNotFound as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Authenticated run history
# ---------------------------------------------------------------------------


@router.get("")
async def list_evaluations(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    return evaluation_service.list_runs(current_user.user_id, limit=limit, offset=offset)


@router.get("/{run_id}")
async def get_evaluation(
    run_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    run = evaluation_service.get_run(current_user.user_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return run


@router.delete("/{run_id}")
async def delete_evaluation(
    run_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    if not evaluation_service.delete_run(current_user.user_id, run_id):
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return {"deleted": True, "run_id": run_id}


@router.delete("")
async def delete_all_evaluations(
    confirm: bool = Query(default=False),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pass confirm=true to delete all evaluation runs for this account",
        )
    deleted_count = evaluation_service.delete_all_runs(current_user.user_id)
    return {"deleted": True, "deleted_count": deleted_count}
