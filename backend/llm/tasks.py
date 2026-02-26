"""
Celery tasks for LLM reasoning generation.
"""

import json
import os
import hashlib
from datetime import datetime
from typing import Any, Dict, List

from celery import Celery
try:
    import redis
except Exception:  # pragma: no cover - optional dependency
    redis = None

from backend.llm.recommendation_reasoning import RecommendationReasoningGenerator
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


@celery_app.task(name="generate_llm_reasoning")
def generate_llm_reasoning(payload: Dict[str, Any]) -> Dict[str, Any]:
    schools_data = payload.get("schools", [])
    player_info = payload.get("player_info", {})
    ml_summary = payload.get("ml_summary", {})
    preferences = payload.get("preferences", {})
    total_matches = payload.get("total_matches", 0)
    min_threshold = payload.get("min_threshold", 5)

    schools = [school_recommendation_from_dict(item) for item in schools_data]

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
        "reasoning": {k: v.__dict__ for k, v in reasoning_map.items()},
        "player_summary": player_summary,
        "relax_suggestions": [s.__dict__ for s in relax_suggestions],
        "completed_at": datetime.now().isoformat(),
    }

    request_hash = payload.get("request_hash")
    if request_hash:
        set_cached_reasoning(
            request_hash,
            result_payload,
            ttl_seconds=int(_get_env("LLM_CACHE_TTL_SECONDS", "3600")),
        )
        clear_inflight_job_id(request_hash)

    return result_payload
