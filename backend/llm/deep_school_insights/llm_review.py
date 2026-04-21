"""LLM reviewer for deep school insights.

Takes a school + player profile + pre-computed evidence and asks the LLM to
interpret that evidence into a ``DeepSchoolReview``. The actual transport is
wrapped by the service via ``_responses_parse``; this module owns only the
prompt construction.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Awaitable, Callable, Dict, Optional

from .evidence import (
    _player_archetype,
    _school_position_family,
    _target_incoming_grad_year,
    _years_until_enrollment,
)
from .types import DeepSchoolReview, GatheredEvidence


logger = logging.getLogger(__name__)


def review_instructions() -> str:
    return (
        "You are a college baseball fit reviewer.\n"
        "You will receive a JSON packet containing:\n"
        "- Pre-computed roster evidence (position counts, departures, openings, transfers)\n"
        "- The player's athletic profile and metrics\n"
        "- The base athletic fit assessment\n\n"
        "Your job is to INTERPRET the evidence and write concise summaries.\n"
        "Use the deterministic athletic metrics as the base layer and use the roster evidence "
        "only to refine the school-level interpretation.\n"
        "Never invent roster facts — all counts and estimates are already computed for you.\n"
        "Treat numeric 0 as an observed zero, not as missing data.\n"
        "Only describe a field as missing if it is null or the literal string 'unknown'.\n"
        "If the roster shows zero players in the target family and position quality is not unknown, "
        "say that no listed players in that family were found; do not say the count was unavailable.\n"
        "If the evidence is thin, keep the base fit unchanged and say so.\n"
        "You may adjust the interpretation by at most one fit level.\n\n"
        "ENROLLMENT TIMING: The player packet includes enrollment_year and "
        "years_until_enrollment. All departure counts and roster projections in the "
        "evidence have already been shifted forward to reflect the roster at arrival. "
        "When years_until_enrollment >= 1, frame your summaries around what the roster "
        "will look like when the player arrives, not what it looks like today. "
        "When years_until_enrollment >= 3, emphasize program size, recruiting patterns, "
        "and historical trends over specific current players since the roster will be "
        "almost entirely turned over by arrival. "
        "If projected_departures_note is present in the roster context, incorporate "
        "that context into your roster_summary and opportunity_summary.\n\n"
        "Write a fit_summary (2-3 sentences on overall fit), program_summary (program context), "
        "roster_summary (roster composition and openings), opportunity_summary (playing time outlook), "
        "and trend_summary (program trajectory). Keep each under 100 words.\n"
        "Populate reasons_for_fit with 2-4 bullet points and risks with 1-3 bullet points."
    )


def review_input(
    school: Dict[str, Any],
    player_stats: Dict[str, Any],
    baseball_assessment: Dict[str, Any],
    academic_score: Dict[str, Any],
    evidence: GatheredEvidence,
) -> str:
    athletic_match = {
        "baseball_fit": school.get("fit_label") or school.get("baseball_fit"),
        "academic_fit": school.get("academic_fit"),
        "delta": school.get("delta"),
        "school_sci": school.get("sci"),
        "ranking_adjustment": school.get("ranking_adjustment"),
        "metric_comparisons": school.get("metric_comparisons", []),
    }
    program_trend = {
        "trend_bonus": school.get("trend_bonus"),
        "trend": school.get("trend"),
        "conference": school.get("conference"),
    }
    position_family = _school_position_family(player_stats.get("primary_position", ""))
    positional_metrics: Dict[str, Any] = {}
    if position_family == "OF":
        positional_metrics["of_velo"] = player_stats.get("of_velo")
    elif position_family == "IF":
        positional_metrics["inf_velo"] = player_stats.get("inf_velo")
    elif position_family == "C":
        positional_metrics["c_velo"] = player_stats.get("c_velo")
        positional_metrics["pop_time"] = player_stats.get("pop_time")

    years_out = _years_until_enrollment(player_stats)
    enrollment_year = _target_incoming_grad_year(player_stats)
    payload = {
        "player": {
            "primary_position": player_stats.get("primary_position"),
            "position_family": position_family,
            "archetype": _player_archetype(player_stats),
            "height": player_stats.get("height"),
            "weight": player_stats.get("weight"),
            "exit_velo_max": player_stats.get("exit_velo_max"),
            "sixty_time": player_stats.get("sixty_time"),
            "enrollment_year": enrollment_year,
            "years_until_enrollment": years_out,
            **positional_metrics,
        },
        "baseball_assessment": baseball_assessment,
        "academic_score": academic_score,
        "athletic_match": athletic_match,
        "program_trend": program_trend,
        "evidence": evidence.model_dump(),
    }
    return (
        "Review this school using the provided evidence packet only.\n"
        f"{json.dumps(payload)}"
    )


async def review_school(
    school: Dict[str, Any],
    player_stats: Dict[str, Any],
    baseball_assessment: Dict[str, Any],
    academic_score: Dict[str, Any],
    evidence: GatheredEvidence,
    *,
    responses_parse: Callable[..., Awaitable[Any]],
    review_model: str,
) -> Optional[DeepSchoolReview]:
    school_name = school.get("display_school_name") or school.get("school_name") or "Unknown School"
    t_start = time.monotonic()
    try:
        response = await responses_parse(
            model=review_model,
            input_text=review_input(
                school,
                player_stats,
                baseball_assessment,
                academic_score,
                evidence,
            ),
            instructions=review_instructions(),
            text_format=DeepSchoolReview,
            max_output_tokens=2500,
        )
    except Exception as exc:
        logger.warning(
            "[TIMING] llm_review school=%r status=failed elapsed=%.2fs err=%s",
            school_name, time.monotonic() - t_start, exc,
        )
        return None
    logger.info(
        "[TIMING] llm_review school=%r status=ok elapsed=%.2fs",
        school_name, time.monotonic() - t_start,
    )
    return getattr(response, "output_parsed", None)
