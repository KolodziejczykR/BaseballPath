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
# Academic-fit penalties (label fallback when no academic_delta is available).
# Philosophy: the real academic cliff is the Strong Safety side (school way
# below student). Safety/Reach/Strong Reach get lighter penalties so the
# matcher still considers them. Magnitudes are ~2x the legacy table so the
# signal actually moves the composite against the 0-100 FIT_FAMILY_BASE swing.
ACADEMIC_FIT_PENALTY_MAP = {
    "strong safety": -9.0,
    "safety": -1.0,
    "fit": 0.0,
    "reach": -2.0,
    "strong reach": -6.5,
}
# When ranking_priority == "academics": the Strong Safety direction is
# effectively excluded via cap in service.py, but kept large here as fallback.
# Reaches are unpenalized (academic stretch is the goal); small hit for
# Strong Reach (probable admit wall).
ACADEMIC_PRIORITY_PENALTY_MAP = {
    "strong safety": -15.0,
    "safety": -5.0,
    "fit": 0.0,
    "reach": 0.0,
    "strong reach": -3.0,
}
# FIT_FAMILY_BASE is now priority-aware. Default (balanced) leaves Safety and
# Reach close to Fit and only docks Strong Safety / Strong Reach.
# baseball_fit makes Reach aspirational and docks Safety (too easy).
# academics docks Reach (academics already stretching, don't double-reach).
FIT_FAMILY_BASE_BY_PRIORITY = {
    None: {
        "Fit": 100.0,
        "Safety": 90.0,
        "Strong Safety": 40.0,
        "Reach": 90.0,
        "Strong Reach": 40.0,
    },
    "baseball_fit": {
        "Fit": 100.0,
        "Safety": 45.0,
        "Strong Safety": 15.0,
        "Reach": 85.0,
        "Strong Reach": 45.0,
    },
    "academics": {
        "Fit": 100.0,
        "Safety": 80.0,
        "Strong Safety": 45.0,
        "Reach": 50.0,
        "Strong Reach": 10.0,
    },
}
# Backwards-compat alias for callers that still import FIT_FAMILY_BASE.
FIT_FAMILY_BASE = FIT_FAMILY_BASE_BY_PRIORITY[None]
PRIORITY_WEIGHTS = {
    None: {"fit_family_base": 1.0, "ranking_score": 1.0, "opportunity_bonus": 0.5, "academic_penalty": 1.0, "academic_quality": 2.0},
    "baseball_fit": {"fit_family_base": 1.3, "ranking_score": 1.2, "opportunity_bonus": 0.25, "academic_penalty": 0.8, "academic_quality": 0.0},
    "academics": {"fit_family_base": 0.7, "ranking_score": 0.6, "opportunity_bonus": 0.15, "academic_penalty": 0.5, "academic_quality": 12.0},
}

# Fallback median academic selectivity score when the player's own academic
# score is unavailable. When the player's score *is* known, the median shifts
# to ``player_score - _ACADEMIC_MEDIAN_OFFSET``, making the quality bonus a
# student-relative signal: schools at or above the student's level are
# rewarded, schools clearly below are penalized.
_ACADEMIC_SELECTIVITY_MEDIAN = 5.0
# How far below the player's academic score the "neutral point" sits. An
# offset of 1.0 means a school one selectivity point below the student
# contributes zero quality bonus; schools at the student's level or above
# contribute positive bonus; Strong Safety territory contributes negative.
_ACADEMIC_MEDIAN_OFFSET = 1.0
# Fallback selectivity value for schools missing an ``academic_selectivity_score``.
# Empirically the ~12-15 schools in the database without a score are all
# academically weak (unranked / open-enrollment / low-selectivity programs),
# so treating them as neutral at the median would over-reward them. 2.5 keeps
# them clearly below the quality-bonus neutral point for any realistic student
# academic score, matching their actual academic profile.
_MISSING_SELECTIVITY_FALLBACK = 2.5
# Attainability scaling on the positive side of the quality bonus. A school's
# prestige is only a useful signal to the extent the student can actually get
# in: Academic Fit / Safety is fully attainable (factor 1.0), Reach is
# aspirational but realistic (0.8), Strong Reach is unlikely admission so
# its prestige shouldn't crown it as the student's best fit (0.35). This is
# what keeps Baseball-Fit + Academic-Reach above Baseball-Fit + Academic-
# Strong-Reach under academics priority.
_QUALITY_BONUS_ATTAINABILITY = {
    "fit": 1.0,
    "safety": 1.0,
    "strong safety": 1.0,
    "reach": 0.8,
    "strong reach": 0.35,
}
VALID_RANKING_PRIORITIES = {"baseball_fit", "academics"}


def _resolve_academic_median(player_academic_score: Optional[float]) -> float:
    """Return the student-relative academic median used to center the quality bonus.

    Falls back to the fixed ``_ACADEMIC_SELECTIVITY_MEDIAN`` when the student's
    own academic score is unknown.
    """
    if player_academic_score is None:
        return _ACADEMIC_SELECTIVITY_MEDIAN
    try:
        return float(player_academic_score) - _ACADEMIC_MEDIAN_OFFSET
    except (TypeError, ValueError):
        return _ACADEMIC_SELECTIVITY_MEDIAN


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _review_confidence_multiplier(value: str) -> float:
    return CONFIDENCE_MULTIPLIER.get((value or "").lower(), 0.35)


def _academic_penalty(academic_delta: float) -> float:
    """Continuous academic penalty that scales with the gap magnitude.

    ``academic_delta`` = player_academic - school_academic.
    Positive means the student is overqualified (safety direction).
    Negative means the school is harder (reach direction).

    Dead zone matches the Fit label cutoff (|Δ| ≤ 0.6). Safety side uses a
    steep exponent so Strong Safety (Δ > 2.0) bites hard; reach side stays
    gentler so aspirational academic reaches remain viable.
    """
    if abs(academic_delta) <= 0.6:
        return 0.0
    if academic_delta > 0.6:
        excess = academic_delta - 0.6
        return -(excess ** 2.2) * 2.2
    else:
        excess = abs(academic_delta) - 0.6
        return -(excess ** 1.5) * 3.0


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
    player_academic_score: Optional[float] = None,
) -> None:
    """Attach family-guarded composite scores and relative opportunity metrics.

    ``player_academic_score`` is the student's effective academic composite
    (0-10 scale). When provided, the academic quality bonus centers on
    ``player_academic_score - _ACADEMIC_MEDIAN_OFFSET`` so the reward/penalty
    split adapts to the individual student rather than the population.
    """
    metrics_by_id = _compute_relative_opportunity_metrics(schools)
    w = PRIORITY_WEIGHTS.get(ranking_priority, PRIORITY_WEIGHTS[None])
    fit_family_table = FIT_FAMILY_BASE_BY_PRIORITY.get(
        ranking_priority, FIT_FAMILY_BASE_BY_PRIORITY[None]
    )
    academic_median = _resolve_academic_median(player_academic_score)

    for school in schools:
        school["raw_opportunity_signal"] = compute_raw_opportunity_signal(school)
        school["relative_opportunity_zscore"] = None
        school["relative_opportunity_bonus"] = 0.0

        acad_label = str(school.get("academic_fit") or "").strip().lower()
        if ranking_priority == "academics":
            school["academic_fit_penalty"] = ACADEMIC_PRIORITY_PENALTY_MAP.get(acad_label, 0.0)
        else:
            acad_delta = school.get("academic_delta")
            if acad_delta is not None:
                school["academic_fit_penalty"] = _academic_penalty(float(acad_delta))
            else:
                school["academic_fit_penalty"] = ACADEMIC_FIT_PENALTY_MAP.get(acad_label, 0.0)

        research_id = school.get("_research_id")
        if research_id is not None:
            metrics = metrics_by_id.get(int(research_id))
            if metrics is not None:
                school.update(metrics)

        fit_label = school.get("fit_label")
        if fit_label not in fit_family_table:
            fit_label = classify_fit(float(school.get("delta") or 0.0))
            school["fit_label"] = fit_label

        # Academic quality bonus: centers on a student-relative median so the
        # reward/penalty scale tracks the individual student's level. Schools
        # missing a selectivity score fall back to _MISSING_SELECTIVITY_FALLBACK
        # (2.5) — the unscored schools in the DB are empirically low-selectivity,
        # so defaulting to neutral would over-reward them.
        raw_selectivity = school.get("academic_selectivity_score")
        if raw_selectivity is None:
            acad_sel = _MISSING_SELECTIVITY_FALLBACK
        else:
            try:
                acad_sel = float(raw_selectivity)
            except (TypeError, ValueError):
                acad_sel = _MISSING_SELECTIVITY_FALLBACK
        # Asymmetric: linear reward above the median (aspirational schools
        # get a steady lift), quadratic penalty below (schools further below
        # the student's level get punished disproportionately, so Lebanon-
        # Valley-tier entries can't coast on small deltas).
        # The positive side is scaled by an attainability factor based on
        # academic fit — Strong-Reach schools get half credit for their
        # selectivity because the student probably can't get in, so the
        # raw prestige is a weaker signal of actual fit.
        selectivity_delta = acad_sel - academic_median
        if selectivity_delta >= 0:
            acad_fit_label_lc = (school.get("academic_fit") or "").strip().lower()
            attainability = _QUALITY_BONUS_ATTAINABILITY.get(acad_fit_label_lc, 1.0)
            acad_quality_bonus = selectivity_delta * w["academic_quality"] * attainability
        else:
            acad_quality_bonus = -(selectivity_delta ** 2) * w["academic_quality"]

        composite = (
            w["fit_family_base"] * fit_family_table[fit_label]
            + w["ranking_score"] * float(school.get("ranking_score") or 0.0)
            + w["opportunity_bonus"] * float(school.get("relative_opportunity_bonus") or 0.0)
            + w["academic_penalty"] * float(school.get("academic_fit_penalty") or 0.0)
            + acad_quality_bonus
        )
        school["cross_school_composite"] = round(composite, 2)
