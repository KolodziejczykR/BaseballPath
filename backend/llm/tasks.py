"""
Celery tasks for deep school research.
"""

import asyncio
import os
import logging
import time
from datetime import datetime
from typing import Any, Dict

from celery import Celery

from backend.llm.deep_school_insights import DeepSchoolInsightService
from backend.api.clients.supabase import get_supabase_admin_client


def _get_env(name: str, default: str) -> str:
    return os.getenv(name, default)


celery_app = Celery(
    "baseballpath_llm",
    broker=_get_env("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=_get_env("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
)

logger = logging.getLogger(__name__)


def _top_schools_snapshot(schools: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    return [
        {"school_name": school.get("display_school_name") or school.get("school_name")}
        for school in (schools or [])[:limit]
    ]


@celery_app.task(
    name="generate_deep_school_research",
    rate_limit=_get_env("DEEP_SCHOOL_TASK_RATE_LIMIT", "12/m"),
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
