"""Deterministic ranking, rerank, and academic penalty scoring.

All functions here are pure — they read numbers out of evidence/review packets
or school dicts and produce floats. They do not touch the network or the LLM.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Sequence, Tuple

from backend.evaluation.competitiveness import classify_fit

from .evidence import _has_meaningful_evidence, _safe_int
from .types import DeepSchoolReview, GatheredEvidence


CONFIDENCE_MULTIPLIER = {"high": 1.0, "medium": 0.7, "low": 0.35}
LEVEL_POINTS = {"high": 8.0, "medium": 3.0, "low": -5.0, "unknown": 0.0}
COMPETITION_POINTS = {"low": 5.0, "medium": 1.0, "high": -5.0, "unknown": 0.0}
OPENING_POINTS = {"high": 4.0, "medium": 2.0, "low": -2.0, "unknown": 0.0}
POSITION_DATA_POINTS = {"exact": 2.0, "mixed": 1.0, "family_only": 0.0, "unknown": 0.0}
ADJUSTMENT_POINTS = {"up_one": 6.0, "none": 0.0, "down_one": -6.0}
MAX_RERANK_ADJUSTMENT = 14.0

# Roster opportunity scoring for the Open / Competitive / Crowded label.
ROSTER_OPPORTUNITY_LEVEL = {"high": 3.0, "medium": 1.0, "low": -2.0, "unknown": 0.0}
ROSTER_COMPETITION_LEVEL = {"low": 2.0, "medium": 0.0, "high": -2.0, "unknown": 0.0}
ROSTER_OPENING_LEVEL = {"high": 3.0, "medium": 1.0, "low": -1.0, "unknown": 0.0}
ROSTER_LABEL_OPEN_THRESHOLD = 4.0
ROSTER_LABEL_CROWDED_THRESHOLD = -2.0

# Bonus added to ranking_adjustment when research produces meaningful evidence.
RESEARCH_QUALITY_BONUS = 1.5

# Cross-school reranking constants.
CROSS_SCHOOL_OPPORTUNITY_WEIGHT = 2.5
CROSS_SCHOOL_Z_CLAMP = 2.5
ACADEMIC_FIT_PENALTY_MAP = {
    "strong safety": -4.0,
    "safety": -1.5,
    "fit": 0.0,
    "reach": -1.75,
    "strong reach": -5.0,
}
FIT_FAMILY_BASE = {
    "Fit": 100.0,
    "Safety": 50.0,
    "Strong Safety": 30.0,
    "Reach": 20.0,
    "Strong Reach": 0.0
}
PRIORITY_WEIGHTS = {
    None: {"fit_family_base": 1.0, "ranking_score": 1.0, "opportunity_bonus": 1.0, "academic_penalty": 1.0},
    "playing_time": {"fit_family_base": 0.8, "ranking_score": 1.0, "opportunity_bonus": 2.0, "academic_penalty": 0.6},
    "baseball_fit": {"fit_family_base": 1.3, "ranking_score": 1.2, "opportunity_bonus": 0.5, "academic_penalty": 0.8},
    "academics": {"fit_family_base": 0.9, "ranking_score": 0.8, "opportunity_bonus": 0.5, "academic_penalty": 2.0},
}
VALID_RANKING_PRIORITIES = {"playing_time", "baseball_fit", "academics"}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _review_confidence_multiplier(value: str) -> float:
    return CONFIDENCE_MULTIPLIER.get((value or "").lower(), 0.35)


def _academic_penalty(academic_delta: float) -> float:
    """Continuous academic penalty that scales with the gap magnitude.

    ``academic_delta`` = player_academic - school_academic.
    Positive means the student is overqualified (safety direction).
    Negative means the school is harder (reach direction).
    """
    if abs(academic_delta) <= 0.9:
        return 0.0
    if academic_delta > 0.9:
        excess = academic_delta - 0.9
        return -(excess ** 1.5) * 1.5
    else:
        excess = abs(academic_delta) - 0.9
        return -(excess ** 1.5) * 1.2


def compute_ranking_adjustment(evidence: GatheredEvidence, review: DeepSchoolReview) -> float:
    roster = evidence.roster_context
    recruiting = evidence.recruiting_context
    opportunity = evidence.opportunity_context

    raw = 0.0
    raw += LEVEL_POINTS.get(opportunity.opportunity_level, 0.0)
    raw += COMPETITION_POINTS.get(opportunity.competition_level, 0.0)
    raw += OPENING_POINTS.get(roster.starter_opening_estimate_same_family, 0.0)
    raw += (OPENING_POINTS.get(roster.starter_opening_estimate_exact_position, 0.0) * 0.75)
    raw += POSITION_DATA_POINTS.get(roster.position_data_quality, 0.0)
    raw += ADJUSTMENT_POINTS.get(review.adjustment_from_base, 0.0)
    raw += min(_safe_int(roster.likely_departures_same_family), 4)
    raw -= min(_safe_int(recruiting.impact_additions_same_family) * 1.5, 5.0)
    raw -= min(_safe_int(recruiting.incoming_same_family_transfers) * 1.0, 3.0)

    scaled = raw * _review_confidence_multiplier(review.confidence)
    return round(_clamp(scaled, -MAX_RERANK_ADJUSTMENT, MAX_RERANK_ADJUSTMENT), 2)


def compute_roster_label(evidence: GatheredEvidence) -> str:
    """Compute a roster opportunity label: ``open``, ``competitive``, or ``crowded``.

    The label is derived deterministically from the gathered roster/recruiting
    evidence.  Schools with no meaningful evidence return ``"unknown"``.
    """
    if not _has_meaningful_evidence(evidence):
        return "unknown"

    roster = evidence.roster_context
    recruiting = evidence.recruiting_context
    opportunity = evidence.opportunity_context

    score = 0.0
    score += ROSTER_OPPORTUNITY_LEVEL.get(opportunity.opportunity_level, 0.0)
    score += ROSTER_COMPETITION_LEVEL.get(opportunity.competition_level, 0.0)
    score += ROSTER_OPENING_LEVEL.get(roster.starter_opening_estimate_same_family, 0.0)
    score += min(_safe_int(roster.likely_departures_same_family), 3) * 1.0
    score -= min(_safe_int(recruiting.incoming_same_family_transfers), 3) * 1.0
    score -= min(_safe_int(recruiting.impact_additions_same_family), 3) * 1.5

    if score >= ROSTER_LABEL_OPEN_THRESHOLD:
        return "open"
    if score < ROSTER_LABEL_CROWDED_THRESHOLD:
        return "crowded"
    return "competitive"


def compute_ranking_score(delta: float, ranking_adjustment: float) -> float:
    """Compute a fit-centered ranking score.

    Schools closest to Fit (delta=0) score highest.  Reaches are slightly
    preferred over equivalent safeties (aspirational > fallback).  The
    ranking_adjustment from roster research can promote or demote a school.
    """
    if delta >= 0:
        fit_distance = delta * 1.0
    else:
        fit_distance = abs(delta) * 0.85
    return round(-fit_distance + ranking_adjustment, 2)


def compute_raw_opportunity_signal(school: Dict[str, Any]) -> Optional[float]:
    """Extract a deterministic roster opportunity signal from a researched school."""
    if school.get("research_status") not in ("completed", "partial"):
        return None

    packet = school.get("research_packet")
    if not isinstance(packet, dict) or not packet:
        return None

    roster = packet.get("roster_context") or {}
    recruiting = packet.get("recruiting_context") or {}
    opportunity = packet.get("opportunity_context") or {}

    signal = 0.0
    signal += LEVEL_POINTS.get(opportunity.get("opportunity_level", "unknown"), 0.0)
    signal += COMPETITION_POINTS.get(opportunity.get("competition_level", "unknown"), 0.0)
    signal += OPENING_POINTS.get(roster.get("starter_opening_estimate_same_family", "unknown"), 0.0)
    signal += OPENING_POINTS.get(roster.get("starter_opening_estimate_exact_position", "unknown"), 0.0) * 0.75
    signal += min(_safe_int(roster.get("likely_departures_same_family")), 4)
    signal -= min(_safe_int(recruiting.get("impact_additions_same_family")) * 1.5, 5.0)
    signal -= min(_safe_int(recruiting.get("incoming_same_family_transfers")) * 1.0, 3.0)
    return round(signal, 2)


def _compute_relative_opportunity_metrics(
    schools: Sequence[Dict[str, Any]],
) -> Dict[int, Dict[str, float]]:
    """Normalize researched-school opportunity signals across the pool."""
    raw_by_id: Dict[int, float] = {}

    for school in schools:
        research_id = school.get("_research_id")
        if research_id is None:
            continue
        raw_signal = compute_raw_opportunity_signal(school)
        if raw_signal is None:
            continue
        raw_by_id[int(research_id)] = float(raw_signal)

    if len(raw_by_id) < 2:
        return {}

    values = list(raw_by_id.values())
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    std_dev = max(math.sqrt(variance), 1.0)

    metrics: Dict[int, Dict[str, float]] = {}
    for research_id, raw_signal in raw_by_id.items():
        z_score = _clamp((raw_signal - mean) / std_dev, -CROSS_SCHOOL_Z_CLAMP, CROSS_SCHOOL_Z_CLAMP)
        metrics[research_id] = {
            "raw_opportunity_signal": round(raw_signal, 2),
            "relative_opportunity_zscore": round(z_score, 4),
            "relative_opportunity_bonus": round(z_score * CROSS_SCHOOL_OPPORTUNITY_WEIGHT, 2),
        }

    return metrics


def _cross_school_sort_key(school: Dict[str, Any]) -> Tuple[float, float, float]:
    return (
        float(school.get("cross_school_composite") or 0.0),
        float(school.get("ranking_score") or 0.0),
        float(school.get("delta") or 0.0),
    )


def _apply_cross_school_reranking(
    schools: Sequence[Dict[str, Any]],
    ranking_priority: Optional[str] = None,
) -> None:
    """Attach family-guarded composite scores and relative opportunity metrics."""
    metrics_by_id = _compute_relative_opportunity_metrics(schools)
    w = PRIORITY_WEIGHTS.get(ranking_priority, PRIORITY_WEIGHTS[None])

    for school in schools:
        school["raw_opportunity_signal"] = compute_raw_opportunity_signal(school)
        school["relative_opportunity_zscore"] = None
        school["relative_opportunity_bonus"] = 0.0

        acad_delta = school.get("academic_delta")
        if acad_delta is not None:
            school["academic_fit_penalty"] = _academic_penalty(float(acad_delta))
        else:
            school["academic_fit_penalty"] = ACADEMIC_FIT_PENALTY_MAP.get(
                str(school.get("academic_fit") or "").strip().lower(),
                0.0,
            )

        research_id = school.get("_research_id")
        if research_id is not None:
            metrics = metrics_by_id.get(int(research_id))
            if metrics is not None:
                school.update(metrics)

        fit_label = school.get("fit_label")
        if fit_label not in FIT_FAMILY_BASE:
            fit_label = classify_fit(float(school.get("delta") or 0.0))
            school["fit_label"] = fit_label

        composite = (
            w["fit_family_base"] * FIT_FAMILY_BASE[fit_label]
            + w["ranking_score"] * float(school.get("ranking_score") or 0.0)
            + w["opportunity_bonus"] * float(school.get("relative_opportunity_bonus") or 0.0)
            + w["academic_penalty"] * float(school.get("academic_fit_penalty") or 0.0)
        )
        school["cross_school_composite"] = round(composite, 2)
