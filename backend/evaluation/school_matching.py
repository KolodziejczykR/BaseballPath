"""
School matching engine for BaseballPath V2 evaluation flow.

This module computes player PCI, compares it against precomputed school SCI,
and assigns baseball fit labels using delta thresholds.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from backend.constants import DIVISION_BENCHMARKS, PITCHER_DIVISION_BENCHMARKS
from backend.evaluation.competitiveness import (
    DEFAULT_DIVISION_MAX_RANKS,
    benchmark_pci,
    classify_fit,
    compute_fit_delta,
    final_pci,
    ml_based_pci,
    normalize_hitter_position,
    normalize_predicted_tier,
    rank_to_percentile,
    to_legacy_fit_label,
    to_national_scale,
)
from backend.utils.school_group_constants import NON_D1, NON_P4_D1, POWER_4_D1

logger = logging.getLogger(__name__)

# Map division_group -> benchmark key used in metric comparison table.
TIER_TO_BENCHMARK_KEY = {
    POWER_4_D1: "P4",
    NON_P4_D1: "Non-P4 D1",
    NON_D1: "Non D1",
}

# Fallback SCI values used only when a school has no rankings-derived SCI.
FALLBACK_SCI_BY_TIER = {
    POWER_4_D1: 78.0,
    NON_P4_D1: 54.0,
    NON_D1: 24.0,
}

# Region -> states mapping (5 regions for preference filtering)
REGION_STATES = {
    "Northeast": {"CT", "ME", "MA", "NH", "RI", "VT", "NJ", "NY", "PA"},
    "Southeast": {"AL", "AR", "DE", "DC", "FL", "GA", "KY", "LA", "MD",
                  "MS", "NC", "SC", "TN", "VA", "WV"},
    "Midwest": {"IL", "IN", "IA", "KS", "MI", "MN", "MO", "NE", "ND",
                "OH", "SD", "WI"},
    "Southwest": {"AZ", "NM", "OK", "TX"},
    "West": {"AK", "CA", "CO", "HI", "ID", "MT", "NV", "OR", "UT", "WA", "WY"},
}

# Budget dropdown -> (min, max) tuples
BUDGET_RANGES = {
    "under_20k": (0, 20000),
    "20k_35k": (20000, 35000),
    "35k_50k": (35000, 50000),
    "50k_65k": (50000, 65000),
    "65k_plus": (65000, None),
    "no_preference": (0, None),
}

# State approximate centroids for map display
STATE_COORDS: Dict[str, Tuple[float, float]] = {
    "AL": (32.8, -86.8), "AK": (64.2, -152.5), "AZ": (34.3, -111.7),
    "AR": (34.8, -92.2), "CA": (37.2, -119.7), "CO": (39.0, -105.5),
    "CT": (41.6, -72.7), "DE": (39.0, -75.5), "DC": (38.9, -77.0),
    "FL": (28.6, -82.4), "GA": (32.7, -83.5), "HI": (20.8, -156.3),
    "ID": (44.4, -114.6), "IL": (40.0, -89.2), "IN": (39.8, -86.3),
    "IA": (42.0, -93.5), "KS": (38.5, -98.3), "KY": (37.8, -85.7),
    "LA": (31.1, -91.9), "ME": (45.4, -69.2), "MD": (39.0, -76.8),
    "MA": (42.2, -71.5), "MI": (44.3, -84.5), "MN": (46.3, -94.3),
    "MS": (32.7, -89.7), "MO": (38.5, -92.2), "MT": (47.0, -109.6),
    "NE": (41.5, -99.8), "NV": (39.9, -116.4), "NH": (43.7, -71.6),
    "NJ": (40.1, -74.7), "NM": (34.5, -106.0), "NY": (42.9, -75.5),
    "NC": (35.6, -79.8), "ND": (47.4, -100.5), "OH": (40.4, -82.8),
    "OK": (35.6, -97.5), "OR": (44.0, -120.5), "PA": (40.9, -77.8),
    "RI": (41.7, -71.5), "SC": (33.9, -80.9), "SD": (44.4, -100.2),
    "TN": (35.9, -86.4), "TX": (31.5, -99.4), "UT": (39.3, -111.7),
    "VT": (44.1, -72.6), "VA": (37.5, -78.9), "WA": (47.4, -120.7),
    "WV": (38.6, -80.6), "WI": (44.6, -89.8), "WY": (43.0, -107.6),
}


def _state_to_region(state: str) -> Optional[str]:
    upper = state.strip().upper()
    for region, states in REGION_STATES.items():
        if upper in states:
            return region
    return None


def _school_division_label(school_tier: str, baseball_division: Any) -> str:
    """
    Display label for school competitive level.
    - Power 4 D1 -> Power 4
    - Non-P4 D1 -> Division 1
    - Non-D1 -> Division 2/Division 3 when baseball_division is available
    - Unknown fallback -> blank (prefer no badge over a misleading Non-D1 tag)
    """
    if school_tier == POWER_4_D1:
        return "Power 4"
    if school_tier == NON_P4_D1:
        return "Division 1"

    try:
        division_num = int(float(baseball_division))
    except (TypeError, ValueError):
        division_num = None

    if division_num == 2:
        return "Division 2"
    if division_num == 3:
        return "Division 3"
    return ""


def _resolve_metric_benchmark_key(school_tier: str, baseball_division: Any) -> str:
    """
    Choose benchmark tier key for metric comparison display.
    Keeps existing mapping for D1 tiers but splits Non-D1 into D2/D3 when available.
    """
    if school_tier == NON_D1:
        try:
            division_num = int(float(baseball_division))
        except (TypeError, ValueError):
            division_num = None
        if division_num == 2:
            return "D2"
        if division_num == 3:
            return "D3"
        return "Non D1"

    return TIER_TO_BENCHMARK_KEY.get(school_tier, "Non-P4 D1")


# ---------------------------------------------------------------------------
# Within-tier percentile for player ML calibration
# ---------------------------------------------------------------------------

def _normal_cdf(z: float) -> float:
    """Approximate standard normal CDF using the error function."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def compute_within_tier_percentile(
    player_stats: Dict[str, Any],
    predicted_tier: str,
    is_pitcher: bool,
) -> float:
    """
    Compute a within-tier percentile (0-100) by averaging stat z-scores against
    the benchmark means/stds for the predicted tier.
    """
    tier = normalize_predicted_tier(predicted_tier)
    benchmark_key = {
        POWER_4_D1: "P4",
        NON_P4_D1: "Non-P4 D1",
        NON_D1: "Non D1",
    }.get(tier, "Non-P4 D1")

    if is_pitcher:
        benchmarks = PITCHER_DIVISION_BENCHMARKS.get(
            benchmark_key, PITCHER_DIVISION_BENCHMARKS.get("Non-P4 D1", {})
        )
        stat_map = {
            "FastballVelocity (max)": player_stats.get("fastball_velo_max"),
            "FastballVelo Range": player_stats.get("fastball_velo_range"),
            "FastballSpin Rate (avg)": player_stats.get("fastball_spin"),
            "Changeup Velo Range": player_stats.get("changeup_velo"),
            "Changeup Spin Rate (avg)": player_stats.get("changeup_spin"),
            "Curveball Velo Range": player_stats.get("curveball_velo"),
            "Curveball Spin Rate (avg)": player_stats.get("curveball_spin"),
            "Slider Velo Range": player_stats.get("slider_velo"),
            "Slider Spin Rate (avg)": player_stats.get("slider_spin"),
        }
    else:
        benchmarks = DIVISION_BENCHMARKS.get(
            benchmark_key, DIVISION_BENCHMARKS.get("Non-P4 D1", {})
        )
        stat_map = {
            "exit_velo": player_stats.get("exit_velo_max"),
            "sixty_time": player_stats.get("sixty_time"),
        }
        if player_stats.get("inf_velo") is not None:
            stat_map["inf_velo"] = player_stats["inf_velo"]
        elif player_stats.get("of_velo") is not None:
            stat_map["of_velo"] = player_stats["of_velo"]
        elif player_stats.get("c_velo") is not None:
            stat_map["c_velo"] = player_stats["c_velo"]
            if player_stats.get("pop_time") is not None:
                stat_map["pop_time"] = player_stats["pop_time"]

    z_scores: List[float] = []
    for stat_name, player_value in stat_map.items():
        if player_value is None:
            continue
        bench = benchmarks.get(stat_name)
        if not bench:
            continue

        mean = bench.get("mean")
        std = bench.get("std")
        if mean is None or std is None or std <= 0:
            continue

        z = (float(player_value) - float(mean)) / float(std)
        if stat_name in ("sixty_time", "pop_time"):
            z = -z  # lower is better
        z_scores.append(z)

    if not z_scores:
        return 50.0

    avg_z = sum(z_scores) / len(z_scores)
    percentile = _normal_cdf(avg_z) * 100.0
    return round(min(max(percentile, 0.0), 100.0), 1)


# ---------------------------------------------------------------------------
# Player PCI computation
# ---------------------------------------------------------------------------

def compute_player_pci(
    player_stats: Dict[str, Any],
    predicted_tier: str,
    d1_probability: Optional[float],
    p4_probability: Optional[float],
    is_pitcher: bool,
) -> Dict[str, Optional[float]]:
    """Compute ML PCI, benchmark PCI, and blended final PCI."""
    normalized_tier = normalize_predicted_tier(predicted_tier)
    within_tier_percentile = compute_within_tier_percentile(
        player_stats=player_stats,
        predicted_tier=normalized_tier,
        is_pitcher=is_pitcher,
    )

    ml_pci = ml_based_pci(
        predicted_tier=normalized_tier,
        within_tier_percentile=within_tier_percentile,
        d1_prob=d1_probability,
        p4_prob=p4_probability,
    )

    if is_pitcher:
        benchmark_pci_value = benchmark_pci(
            player_metrics=player_stats,
            player_type="pitcher",
            player_position="P",
            predicted_tier=normalized_tier,
        )
    else:
        benchmark_pci_value = benchmark_pci(
            player_metrics=player_stats,
            player_type="hitter",
            player_position=normalize_hitter_position(player_stats.get("primary_position")),
            predicted_tier=normalized_tier,
        )

    blended = final_pci(ml_pci, benchmark_pci_value)

    return {
        "predicted_tier": normalized_tier,
        "within_tier_percentile": round(within_tier_percentile, 1),
        "ml_pci": round(ml_pci, 2),
        "benchmark_pci": (round(benchmark_pci_value, 2) if benchmark_pci_value is not None else None),
        "player_pci": round(blended, 2),
    }


# ---------------------------------------------------------------------------
# School SCI + academic fit
# ---------------------------------------------------------------------------

def _resolve_school_sci(school: Dict[str, Any], is_pitcher: bool) -> Tuple[Optional[float], float]:
    """
    Resolve school SCI and trend bonus.

    Priority:
    1. Precomputed SCI from enrichment cache.
    2. Percentile + division fallback mapping.
    3. Tier-level fallback constant.
    """
    sci_key = "baseball_sci_pitcher" if is_pitcher else "baseball_sci_hitter"
    sci_value = school.get(sci_key)
    if sci_value is None:
        # Compatibility for alternative key naming.
        alt_key = "sci_pitcher" if is_pitcher else "sci_hitter"
        sci_value = school.get(alt_key)

    trend_bonus = school.get("baseball_trend_bonus")
    if trend_bonus is None:
        trend_bonus = school.get("trend_bonus", 0.0)

    try:
        trend_value = float(trend_bonus)
    except (TypeError, ValueError):
        trend_value = 0.0

    if sci_value is not None:
        try:
            return float(sci_value), trend_value
        except (TypeError, ValueError):
            pass

    division = school.get("baseball_division") or school.get("division")
    percentile = school.get("baseball_division_percentile")
    if percentile is not None and division is not None:
        national = to_national_scale(percentile, division)
        if national is not None:
            return float(national), trend_value

    overall_rating = school.get("baseball_overall_rating")
    if overall_rating is not None and division is not None:
        try:
            division_key = str(int(float(division)))
        except (TypeError, ValueError):
            division_key = str(division).strip()
        max_rank = DEFAULT_DIVISION_MAX_RANKS.get(division_key)
        if max_rank:
            pct = rank_to_percentile(overall_rating, max_rank)
            national = to_national_scale(pct, division)
            if national is not None:
                return float(national), trend_value

    school_tier = school.get("division_group", NON_D1)
    return float(FALLBACK_SCI_BY_TIER.get(school_tier, FALLBACK_SCI_BY_TIER[NON_D1])), trend_value


def _academic_fit_label(
    player_academic_rating: float,
    school_academic_rating: Optional[float],
) -> Optional[str]:
    """
    Determine academic fit from delta = player - school.

    Positive delta → player exceeds school selectivity (safety).
    Negative delta → school is more selective (reach).
    """
    if school_academic_rating is None:
        return "fit"

    delta = player_academic_rating - school_academic_rating

    if delta > 1.6:
        return "strong_safety"
    if delta >= 0.8:
        return "safety"
    if delta >= -0.8:
        return "fit"
    if delta >= -1.6:
        return "reach"
    # Strong reach academically — exclude
    return None


# ---------------------------------------------------------------------------
# Main matching pipeline
# ---------------------------------------------------------------------------

def match_and_rank_schools(
    schools: List[Dict[str, Any]],
    player_stats: Dict[str, Any],
    predicted_tier: str,
    player_pci: float,
    academic_composite: float,
    is_pitcher: bool,
    selected_regions: Optional[List[str]] = None,
    max_budget: Optional[int] = None,
    user_state: Optional[str] = None,
    limit: int = 15,
    consideration_pool: bool = False,
) -> List[Dict[str, Any]]:
    """
    Match schools against player PCI, apply filters, and return a balanced list.

    When ``consideration_pool=True``, the function returns a broader candidate
    set (wider delta range, relaxed exclusion rules) intended for downstream
    roster research that will perform final selection.
    """
    player_academic_rounded = academic_composite
    candidates: List[Dict[str, Any]] = []

    allowed_states = None
    if selected_regions:
        allowed_states = set()
        for region in selected_regions:
            allowed_states.update(REGION_STATES.get(region, set()))

    for school in schools:
        school_name = school.get("school_name", "")
        display_school_name = (school.get("display_school_name") or school_name or "").strip()
        if not display_school_name:
            display_school_name = school_name
        school_tier = school.get("division_group", NON_D1)
        school_state = (school.get("school_state") or "").strip().upper()
        baseball_division = school.get("baseball_division")

        # Preference filter: region
        if allowed_states is not None and school_state not in allowed_states:
            continue

        # Preference filter: budget
        if max_budget is not None and user_state:
            user_st = user_state.strip().upper()
            tuition = school.get("in_state_tuition") if school_state == user_st else school.get("out_of_state_tuition")
            if tuition is not None and tuition > max_budget:
                continue
        elif max_budget is not None:
            tuition = school.get("out_of_state_tuition")
            if tuition is not None and tuition > max_budget:
                continue

        school_sci, trend_bonus = _resolve_school_sci(school, is_pitcher=is_pitcher)
        if school_sci is None:
            continue

        delta = compute_fit_delta(player_pci, school_sci)

        # Skip extreme mismatches.
        if consideration_pool:
            if delta > 20 or delta < -18:
                continue
        else:
            if delta > 25 or delta < -20:
                continue

        fit_label = classify_fit(delta)
        baseball_fit = to_legacy_fit_label(fit_label)

        school_selectivity = school.get("academic_selectivity_score")
        if school_selectivity is not None:
            try:
                school_acad_numeric: Optional[float] = float(school_selectivity)
            except (TypeError, ValueError):
                school_acad_numeric = 2.0
        else:
            school_acad_numeric = 2.0
        acad_label = _academic_fit_label(player_academic_rounded, school_acad_numeric)
        if acad_label is None:
            continue

        if not consideration_pool:
            # Keep obvious double-reach schools out, but allow ordinary
            # safety/safety combinations to surface as true fallback options.
            # In consideration_pool mode, let roster research decide.
            if baseball_fit == "reach" and acad_label == "reach":
                continue
            if fit_label == "Strong Safety" and acad_label in ("safety", "strong_safety"):
                continue

        if user_state:
            user_st = user_state.strip().upper()
            display_tuition = school.get("in_state_tuition") if school_state == user_st else school.get("out_of_state_tuition")
        else:
            display_tuition = school.get("out_of_state_tuition")

        metric_comparisons = _build_metric_comparisons(
            player_stats=player_stats,
            school_tier=school_tier,
            baseball_division=baseball_division,
            is_pitcher=is_pitcher,
        )
        school_region = _state_to_region(school_state) if school_state else None
        coords = STATE_COORDS.get(school_state, (0.0, 0.0))

        candidates.append({
            "school_name": school_name,
            "display_school_name": display_school_name,
            "school_logo_image": school.get("school_logo_image"),
            "conference": school.get("conference"),
            "division_group": school_tier,
            "baseball_division": baseball_division,
            "division_label": _school_division_label(school_tier, baseball_division),
            "location": {
                "state": school_state,
                "region": school_region,
                "latitude": coords[0],
                "longitude": coords[1],
            },
            "baseball_fit": baseball_fit,
            "fit_label": fit_label,
            "academic_fit": acad_label,
            "niche_academic_grade": school_acad_grade,
            "estimated_annual_cost": display_tuition,
            "metric_comparisons": metric_comparisons,
            "delta": round(delta, 2),
            "sci": round(float(school_sci), 2),
            "trend": f"{trend_bonus:+.2f}",
            "trend_bonus": round(trend_bonus, 2),
            "_abs_delta": abs(delta),
        })

    logger.info(
        "School matching produced %s candidates (%s fit / %s safety / %s reach / %s strong-safety / %s strong-reach)%s",
        len(candidates),
        len([c for c in candidates if c["fit_label"] == "Fit"]),
        len([c for c in candidates if c["fit_label"] == "Safety"]),
        len([c for c in candidates if c["fit_label"] == "Reach"]),
        len([c for c in candidates if c["fit_label"] == "Strong Safety"]),
        len([c for c in candidates if c["fit_label"] == "Strong Reach"]),
        " (consideration pool)" if consideration_pool else "",
    )

    if consideration_pool:
        # Consideration pool: return all candidates sorted by closeness to
        # fit, up to limit.  Downstream roster research handles final
        # selection — no balanced-category logic needed here.
        candidates.sort(key=lambda x: x["_abs_delta"])
        selected = candidates[:limit]
    else:
        # Exclude strong outliers by default, unless there are no regular candidates.
        regular_candidates = [
            c for c in candidates if c["fit_label"] in {"Safety", "Fit", "Reach"}
        ]
        working_set = regular_candidates if regular_candidates else candidates

        working_set.sort(key=lambda x: x["_abs_delta"])

        reaches = [c for c in working_set if c["fit_label"] == "Reach"]
        fits = [c for c in working_set if c["fit_label"] == "Fit"]
        safeties = [c for c in working_set if c["fit_label"] == "Safety"]

        selected: List[Dict[str, Any]] = []
        target_fits = min(8, limit)
        selected.extend(fits[:target_fits])

        remaining = limit - len(selected)
        if remaining > 0:
            selected.extend(safeties[: min(4, remaining)])

        remaining = limit - len(selected)
        if remaining > 0:
            selected.extend(reaches[:remaining])

        # Backfill from all unused candidates if we still have room.
        if len(selected) < limit:
            selected_names = {s["school_name"] for s in selected}
            backfill = [c for c in candidates if c["school_name"] not in selected_names]
            backfill.sort(key=lambda x: (x["_abs_delta"], -x["delta"]))
            selected.extend(backfill[: limit - len(selected)])

    selected.sort(key=lambda x: x["delta"], reverse=True)

    results: List[Dict[str, Any]] = []
    for i, school in enumerate(selected[:limit]):
        school.pop("_abs_delta", None)
        school["rank"] = i + 1
        results.append(school)

    return results


def _build_metric_comparisons(
    player_stats: Dict[str, Any],
    school_tier: str,
    baseball_division: Any,
    is_pitcher: bool,
) -> List[Dict[str, Any]]:
    """Build metric comparison table for explainability."""
    benchmark_key = _resolve_metric_benchmark_key(school_tier, baseball_division)
    comparisons = []

    if is_pitcher:
        benchmarks = PITCHER_DIVISION_BENCHMARKS.get(benchmark_key, {})
        metrics = [
            ("Fastball Velocity", "fastball_velo_max", "FastballVelocity (max)", "mph"),
            ("Fastball Spin", "fastball_spin", "FastballSpin Rate (avg)", "rpm"),
            ("Changeup Velocity", "changeup_velo", "Changeup Velo Range", "mph"),
            ("Curveball Velocity", "curveball_velo", "Curveball Velo Range", "mph"),
            ("Slider Velocity", "slider_velo", "Slider Velo Range", "mph"),
        ]
    else:
        benchmarks = DIVISION_BENCHMARKS.get(benchmark_key, {})
        metrics = [
            ("Exit Velocity", "exit_velo_max", "exit_velo", "mph"),
            ("60-Yard Dash", "sixty_time", "sixty_time", "sec"),
        ]
        if player_stats.get("inf_velo") is not None:
            metrics.append(("Infield Velocity", "inf_velo", "inf_velo", "mph"))
        elif player_stats.get("of_velo") is not None:
            metrics.append(("Outfield Velocity", "of_velo", "of_velo", "mph"))
        elif player_stats.get("c_velo") is not None:
            metrics.append(("Catcher Velocity", "c_velo", "c_velo", "mph"))
            if player_stats.get("pop_time") is not None:
                metrics.append(("Pop Time", "pop_time", "pop_time", "sec"))

    for display_name, player_key, bench_key, unit in metrics:
        player_val = player_stats.get(player_key)
        if player_val is None:
            continue
        bench = benchmarks.get(bench_key)
        if not bench:
            continue
        try:
            player_num = round(float(player_val), 1)
            bench_num = round(float(bench["mean"]), 1)
        except (TypeError, ValueError, KeyError):
            continue

        comparisons.append({
            "metric": display_name,
            "player_value": player_num,
            "division_avg": bench_num,
            "unit": unit,
        })

    return comparisons
