"""
Celery tasks for LLM reasoning generation.
"""

import asyncio
import json
import os
import hashlib
import logging
import time
from datetime import datetime
from typing import Any, Dict

from celery import Celery
try:
    import redis
except Exception:  # pragma: no cover - optional dependency
    redis = None

from backend.llm.recommendation_reasoning import (
    InsufficientQuotaError,
    RecommendationReasoningGenerator,
)
from backend.llm.deep_school_insights import DeepSchoolInsightService
from backend.api.clients.supabase import get_supabase_admin_client
from backend.utils.recommendation_types import school_recommendation_from_dict


def _get_env(name: str, default: str) -> str:
    return os.getenv(name, default)


celery_app = Celery(
    "baseballpath_llm",
    broker=_get_env("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=_get_env("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
)

CACHE_PREFIX = "llm:reasoning:"
INFLIGHT_PREFIX = "llm:reasoning:inflight:"
logger = logging.getLogger(__name__)


def _top_schools_snapshot(schools: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    return [
        {"school_name": school.get("display_school_name") or school.get("school_name")}
        for school in (schools or [])[:limit]
    ]


def compute_request_hash(payload: Dict[str, Any]) -> str:
    normalized = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _redis_client():
    if redis is None:
        return None
    url = _get_env("REDIS_URL", "redis://localhost:6379/2")
    return redis.Redis.from_url(url, decode_responses=True)


def get_cached_reasoning(request_hash: str) -> Dict[str, Any] | None:
    client = _redis_client()
    if client is None:
        return None
    data = client.get(f"{CACHE_PREFIX}{request_hash}")
    if not data:
        return None
    try:
        return json.loads(data)
    except Exception:
        return None


def set_cached_reasoning(request_hash: str, payload: Dict[str, Any], ttl_seconds: int = 3600) -> None:
    client = _redis_client()
    if client is None:
        return None
    client.setex(f"{CACHE_PREFIX}{request_hash}", ttl_seconds, json.dumps(payload, ensure_ascii=True))


def get_inflight_job_id(request_hash: str) -> str | None:
    client = _redis_client()
    if client is None:
        return None
    return client.get(f"{INFLIGHT_PREFIX}{request_hash}")


def set_inflight_job_id(request_hash: str, job_id: str, ttl_seconds: int = 900) -> None:
    client = _redis_client()
    if client is None:
        return None
    client.setex(f"{INFLIGHT_PREFIX}{request_hash}", ttl_seconds, job_id)


def clear_inflight_job_id(request_hash: str) -> None:
    client = _redis_client()
    if client is None:
        return None
    client.delete(f"{INFLIGHT_PREFIX}{request_hash}")


@celery_app.task(
    name="generate_llm_reasoning",
    rate_limit=_get_env("LLM_TASK_RATE_LIMIT", "30/m"),
)
def generate_llm_reasoning(payload: Dict[str, Any]) -> Dict[str, Any]:
    request_hash = payload.get("request_hash")
    schools_data = payload.get("schools", [])
    player_info = payload.get("player_info", {})
    ml_summary = payload.get("ml_summary", {})
    preferences = payload.get("preferences", {})
    total_matches = payload.get("total_matches", 0)
    min_threshold = payload.get("min_threshold", 5)

    schools = [school_recommendation_from_dict(item) for item in schools_data]

    try:
        generator = RecommendationReasoningGenerator()
        reasoning_map = generator.generate_school_reasoning(
            schools,
            player_info=player_info,
            ml_summary=ml_summary,
            preferences=preferences,
            batch_size=5,
        )

        player_summary = None
        if payload.get("include_player_summary"):
            player_summary = generator.generate_player_summary(
                schools,
                player_info=player_info,
                ml_summary=ml_summary,
                preferences=preferences,
            )

        relax_suggestions = generator.generate_relax_suggestions(
            must_haves=payload.get("must_haves", {}),
            total_matches=total_matches,
            min_threshold=min_threshold,
        )

        result_payload = {
            "status": "completed",
            "reasoning": {k: v.__dict__ for k, v in reasoning_map.items()},
            "player_summary": player_summary,
            "relax_suggestions": [s.__dict__ for s in relax_suggestions],
            "completed_at": datetime.now().isoformat(),
        }
    except InsufficientQuotaError as exc:
        logger.warning("LLM reasoning unavailable (insufficient quota): %s", exc)
        result_payload = {
            "status": "failed",
            "error_code": "insufficient_quota",
            "error_message": "LLM quota exceeded. Please check billing and usage limits.",
            "reasoning": {},
            "player_summary": None,
            "relax_suggestions": [],
            "completed_at": datetime.now().isoformat(),
        }
    except Exception as exc:
        logger.exception("LLM reasoning task failed: %s", exc)
        result_payload = {
            "status": "failed",
            "error_code": "llm_generation_error",
            "error_message": "LLM reasoning generation failed.",
            "reasoning": {},
            "player_summary": None,
            "relax_suggestions": [],
            "completed_at": datetime.now().isoformat(),
        }

    if request_hash:
        try:
            set_cached_reasoning(
                request_hash,
                result_payload,
                ttl_seconds=int(_get_env("LLM_CACHE_TTL_SECONDS", "3600")),
            )
        finally:
            clear_inflight_job_id(request_hash)

    return result_payload


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
