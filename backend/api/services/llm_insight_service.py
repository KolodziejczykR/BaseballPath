"""
LLM insight helpers for the finalize pipeline.

Two separate responsibilities:
  * Synchronous per-school summaries (`apply_basic_school_insights`) — used
    when inline LLM calls are desired.
  * Background deep roster research (`enqueue_deep_school_research`) — hands
    off to Celery.

No FastAPI dependencies; routers import these and handle HTTP concerns.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from ..clients.supabase import require_supabase_admin_client

logger = logging.getLogger(__name__)


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


def _build_llm_insights_prompt(
    schools: List[Dict[str, Any]],
    player_stats: Dict[str, Any],
    predicted_tier: str,
    academic_score: Dict[str, Any],
    is_pitcher: bool,
) -> str:
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


def call_llm_insights(
    schools: List[Dict[str, Any]],
    player_stats: Dict[str, Any],
    predicted_tier: str,
    academic_score: Dict[str, Any],
    is_pitcher: bool,
) -> Dict[str, Dict[str, str]]:
    """Call LLM for batched school insights. Returns {school_name: {fit_summary, school_description}}."""
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

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1:
                data = json.loads(content[start:end + 1])
            else:
                return {}

        result: Dict[str, Dict[str, str]] = {}
        for item in data.get("schools", []):
            name = item.get("school_name")
            if name:
                result[name] = {
                    "fit_summary": item.get("fit_summary", ""),
                    "school_description": item.get("school_description", ""),
                }
        return result
    except Exception as exc:
        logger.error("LLM insights call failed: %s", exc)
        return {}


def apply_basic_school_insights(
    schools: List[Dict[str, Any]],
    player_stats: Dict[str, Any],
    baseball_assessment: Dict[str, Any],
    academic_score: Dict[str, Any],
    is_pitcher: bool,
) -> List[Dict[str, Any]]:
    if not schools:
        return schools

    working = [dict(school) for school in schools]
    insights = call_llm_insights(
        working,
        player_stats,
        baseball_assessment["predicted_tier"],
        academic_score,
        is_pitcher,
    )
    for school in working:
        school_insight = insights.get(school["school_name"], {})
        school["fit_summary"] = school_insight.get("fit_summary", "")
        school["school_description"] = school_insight.get("school_description", "")
    return working


def should_enqueue_deep_school_research(schools: List[Dict[str, Any]]) -> bool:
    return bool(
        _openai_client is not None and generate_deep_school_research is not None and schools
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
