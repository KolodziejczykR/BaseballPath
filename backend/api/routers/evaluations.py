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

NOTE: this module deliberately does NOT use ``from __future__ import
annotations``. SlowAPI's ``@limiter.limit`` decorator wraps route handlers
in a way that confuses FastAPI's introspection when annotations are
deferred (string ForwardRefs). Concretely, ``payload: EvaluateRequest``
under future-annotations gets registered as ``Body(PydanticUndefined)``
with an unresolvable ForwardRef, which breaks OpenAPI generation and
request validation. Keeping annotations evaluated at definition time
side-steps the issue.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from ..deps.auth import AuthenticatedUser, get_current_user, get_optional_user
from ..rate_limit import limiter
from ..services import evaluation_service
from ..services.evaluation_service import (
    DISCLAIMER_TEXT,
    EvaluateRequest,
    EvaluationInputError,
    LegacyPositionTrackConstraintError,
    PendingEvaluationNotFound,
    PredictionRunPersistError,
    PurchaseAlreadyUsed,
    PurchaseNotFound,
    PurchaseNotPaid,
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
# Rate limit: the preview endpoint runs the full ML pipeline + matcher,
# which is non-trivial work. This is the most expensive anonymous route
# we serve, so we enforce a per-IP cap. 30/minute is well above what a
# real user (one preview per session, maybe a tweak) would hit, low
# enough that scripted abuse would notice.
@limiter.limit("30/minute")
async def preview_evaluation(
    request: Request,  # noqa: ARG001 — required by SlowAPI for IP keying
    # Explicit Body() marker because the @limiter.limit wrapper combined
    # with `from __future__ import annotations` confuses FastAPI's
    # body-vs-query inference and would otherwise register the param as
    # a query string, breaking OpenAPI generation and routing.
    payload: EvaluateRequest = Body(...),
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

    teaser_schools = evaluation_service.build_teaser(
        core, ranking_priority=payload.preferences.ranking_priority,
    )

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
    except PurchaseNotPaid as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc)) from exc
    except PurchaseAlreadyUsed as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
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
