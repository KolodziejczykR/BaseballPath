"""
Celery tasks for deep school research.
"""

import asyncio
import os
import logging
import time
from datetime import datetime
from typing import Any, Dict

import sentry_sdk
from celery import Celery

from backend.observability import init_sentry
from backend.llm.deep_school_insights import DeepSchoolInsightService
from backend.api.clients.supabase import get_supabase_admin_client


# Sentry must be initialized before any task code can throw — the worker
# is a separate process from the FastAPI app, so init_sentry() in main.py
# does not cover us here.
init_sentry(with_celery=True)


logger = logging.getLogger(__name__)


def _resolve_broker_url(default_db: str) -> str:
    """Resolve the broker / result-backend URL with explicit guards.

    Render's convention is REDIS_URL; we also accept CELERY_BROKER_URL /
    CELERY_RESULT_BACKEND for explicit control. If neither is set AND we
    appear to be in a non-development environment, fail loudly so the
    misconfiguration is impossible to miss — silently falling back to
    redis://localhost:6379 in production was the previous failure mode
    and produced a worker that quietly couldn't reach a real broker.
    """
    explicit = (
        os.getenv("CELERY_BROKER_URL")
        if default_db.endswith("/0")
        else os.getenv("CELERY_RESULT_BACKEND")
    )
    if explicit:
        return explicit

    # Fall back to REDIS_URL if Render-style env is set.
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        # REDIS_URL points at the base instance; we partition by db number.
        if redis_url.endswith("/"):
            return redis_url + default_db.lstrip("/")
        return f"{redis_url.rstrip('/')}/{default_db.lstrip('/').split('/')[-1]}"

    # Nothing configured. Localhost fallback is OK only in dev.
    environment = os.getenv("ENVIRONMENT", "development").lower()
    if environment != "development":
        msg = (
            f"Neither CELERY_BROKER_URL nor REDIS_URL is set in "
            f"environment={environment!r}. Celery cannot reach a broker; "
            f"deep school research tasks will fail. Refusing to start with "
            f"localhost fallback."
        )
        logger.critical(msg)
        # Raise so the worker process exits with a clear signal instead
        # of pretending to be healthy while silently broken. The web
        # process imports this module too, but only via tasks.py being
        # imported on demand — main.py does not import tasks.py at boot.
        raise RuntimeError(msg)

    logger.warning(
        "CELERY_BROKER_URL / REDIS_URL not set; using localhost fallback "
        "(environment=%s). This is fine in dev; set it in prod.",
        environment,
    )
    return f"redis://localhost:6379{default_db}"


celery_app = Celery(
    "baseballpath_llm",
    broker=_resolve_broker_url("/0"),
    backend=_resolve_broker_url("/1"),
)

celery_app.conf.broker_transport_options = {
    "socket_keepalive": True,
    "socket_keepalive_options": {},
    "visibility_timeout": 3600,
}
celery_app.conf.broker_connection_retry_on_startup = True
# Survive worker restarts. Render redeploys the worker process on every
# code push — a task that was mid-flight when the worker pod was killed
# would be silently dropped under the default acks_late=False, leaving
# the prediction_run stuck in 'processing' forever. With acks_late=True,
# the broker holds onto the task until the worker explicitly acks (after
# success), so a killed worker re-queues automatically and the new pod
# picks it up. Safe because generate_deep_school_research is idempotent
# (checks llm_reasoning_status at the top before doing any work).
celery_app.conf.task_acks_late = True
celery_app.conf.task_reject_on_worker_lost = True


# Statuses that indicate the task already finished successfully (or was
# intentionally skipped). A retry firing against a run in any of these
# states would clobber the persisted result — return early instead.
_TERMINAL_LLM_STATUSES = frozenset({"completed", "skipped", "failed"})

def _top_schools_snapshot(schools: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    return [
        {"school_name": school.get("display_school_name") or school.get("school_name")}
        for school in (schools or [])[:limit]
    ]


@celery_app.task(
    name="generate_deep_school_research",
    rate_limit=os.getenv("DEEP_SCHOOL_TASK_RATE_LIMIT", "12/m"),
)
def generate_deep_school_research(payload: Dict[str, Any]) -> Dict[str, Any]:
    run_id = payload.get("run_id")
    schools = payload.get("schools") or []
    player_stats = payload.get("player_stats") or {}
    baseball_assessment = payload.get("baseball_assessment") or {}
    academic_score = payload.get("academic_score") or {}
    final_limit = payload.get("final_limit")
    ranking_priority = payload.get("ranking_priority")

    supabase = get_supabase_admin_client()
    if supabase is None:
        logger.error("Deep school research cannot run without Supabase admin client")
        return {"status": "failed", "error": "supabase_not_configured", "run_id": run_id}

    # Idempotency guard: if this task has already finished for this run,
    # don't re-run. Celery retries fire on transient broker / worker /
    # network failures — but our task does ~30+ LLM calls per run, so a
    # retry that overwrites a fresh result is both expensive and risks
    # clobbering data the user has already started reading.
    if run_id:
        existing = (
            supabase.table("prediction_runs")
            .select("llm_reasoning_status")
            .eq("id", run_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            current_status = existing.data[0].get("llm_reasoning_status")
            if current_status in _TERMINAL_LLM_STATUSES:
                logger.info(
                    "Deep school research already %s for run %s — "
                    "skipping retry (idempotency guard)",
                    current_status, run_id,
                )
                return {
                    "status": "skipped",
                    "run_id": run_id,
                    "reason": "already_terminal",
                    "previous_status": current_status,
                }

    service = DeepSchoolInsightService()
    if not service.enabled:
        supabase.table("prediction_runs").update(
            {"llm_reasoning_status": "skipped"}
        ).eq("id", run_id).execute()
        return {"status": "skipped", "run_id": run_id}

    t_task_start = time.monotonic()
    logger.info(
        "[TIMING] deep_school_task start run_id=%s schools=%d final_limit=%s",
        run_id, len(schools), final_limit,
    )
    try:
        enriched_schools = asyncio.run(
            service.enrich_and_rerank(
                schools=schools,
                player_stats=player_stats,
                baseball_assessment=baseball_assessment,
                academic_score=academic_score,
                final_limit=final_limit,
                ranking_priority=ranking_priority,
            )
        )
        logger.info(
            "[TIMING] deep_school_task enrich_done run_id=%s elapsed=%.2fs",
            run_id, time.monotonic() - t_task_start,
        )

        current_run = (
            supabase.table("prediction_runs")
            .select("preferences_response")
            .eq("id", run_id)
            .limit(1)
            .execute()
        )
        if not current_run.data:
            raise RuntimeError(f"prediction_run {run_id} not found")

        preferences_response = current_run.data[0].get("preferences_response") or {}
        preferences_response["schools"] = enriched_schools

        # Compute honest completion status from per-school outcomes
        total = len(enriched_schools)
        succeeded = sum(
            1 for s in enriched_schools
            if s.get("research_status") in ("completed", "partial")
        )
        if total == 0:
            llm_status = "skipped"
        elif succeeded == 0:
            llm_status = "failed"
        else:
            llm_status = "completed"

        supabase.table("prediction_runs").update(
            {
                "preferences_response": preferences_response,
                "top_schools_snapshot": _top_schools_snapshot(enriched_schools),
                "llm_reasoning_status": llm_status,
            }
        ).eq("id", run_id).execute()

        logger.info(
            "[TIMING] deep_school_task done run_id=%s status=%s total=%.2fs",
            run_id, llm_status, time.monotonic() - t_task_start,
        )
        return {
            "status": llm_status,
            "run_id": run_id,
            "school_count": total,
            "schools_enriched": succeeded,
            "completed_at": datetime.now().isoformat(),
        }
    except Exception as exc:
        logger.exception("Deep school research task failed for run %s: %s", run_id, exc)
        supabase.table("prediction_runs").update(
            {"llm_reasoning_status": "failed"}
        ).eq("id", run_id).execute()
        return {
            "status": "failed",
            "run_id": run_id,
            "error": str(exc),
            "completed_at": datetime.now().isoformat(),
        }
