"""
LLM insight helpers for the finalize pipeline.

Hands off deep roster research to the Celery worker via
``enqueue_deep_school_research``.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from ..clients.supabase import require_supabase_admin_client

logger = logging.getLogger(__name__)

_has_openai = bool(os.getenv("OPENAI_API_KEY"))

try:
    from backend.llm.tasks import generate_deep_school_research
except Exception:
    generate_deep_school_research = None


def should_enqueue_deep_school_research(schools: List[Dict[str, Any]]) -> bool:
    return bool(
        _has_openai and generate_deep_school_research is not None and schools
    )


def attach_roster_urls(schools: List[Dict[str, Any]]) -> None:
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
        url_map = {
            row["school_name"]: row["baseball_roster_url"]
            for row in (resp.data or [])
            if row.get("baseball_roster_url")
        }
        for school in schools:
            name = school.get("school_name", "")
            if name in url_map:
                school["roster_url"] = url_map[name]
    except Exception as exc:
        logger.warning("Failed to look up roster URLs: %s", exc)


def enqueue_deep_school_research(
    *,
    run_id: str,
    schools: List[Dict[str, Any]],
    player_stats: Dict[str, Any],
    baseball_assessment: Dict[str, Any],
    academic_score: Dict[str, Any],
    final_limit: Optional[int] = None,
    ranking_priority: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    if not should_enqueue_deep_school_research(schools):
        return "skipped", None

    attach_roster_urls(schools)

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
        if ranking_priority is not None:
            payload["ranking_priority"] = ranking_priority
        job = generate_deep_school_research.delay(payload)
        return "processing", getattr(job, "id", None)
    except Exception as exc:
        logger.warning("Failed to enqueue deep school research for run %s: %s", run_id, exc)
        return "failed", None
