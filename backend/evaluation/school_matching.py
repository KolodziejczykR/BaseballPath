"""
School matching engine for BaseballPath V2 evaluation flow.

This module computes player PCI, compares it against precomputed school SCI,
and assigns baseball fit labels using delta thresholds.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from backend.constants import DIVISION_BENCHMARKS, PITCHER_DIVISION_BENCHMARKS, get_position_benchmarks
from backend.evaluation.competitiveness import (
    DEFAULT_DIVISION_MAX_RANKS,
    classify_fit,
    compute_fit_delta,
    final_pci,
    ml_based_pci,
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


def _average_benchmarks(
    bench_a: Dict[str, Dict[str, float]],
    bench_b: Dict[str, Dict[str, float]],
) -> Dict[str, Dict[str, float]]:
    """Average mean/std from two benchmark dicts (e.g. D2 + D3 for Non-D1)."""
    result: Dict[str, Dict[str, float]] = {}
    all_keys = set(bench_a) | set(bench_b)
    for key in all_keys:
        a = bench_a.get(key)
        b = bench_b.get(key)
        if a and b:
            result[key] = {
                "mean": (a["mean"] + b["mean"]) / 2.0,
                "std": (a["std"] + b["std"]) / 2.0,
            }
        elif a:
            result[key] = dict(a)
        elif b:
            result[key] = dict(b)
    return result


def _resolve_tier_benchmarks_for_percentile(
    tier: str,
    is_pitcher: bool,
    player_position: str,
) -> Dict[str, Dict[str, float]]:
    """Resolve the benchmark dict for a given tier, averaging D2+D3 for Non-D1."""
    benchmark_key = {
        POWER_4_D1: "P4",
        NON_P4_D1: "Non-P4 D1",
    }.get(tier)

    if is_pitcher:
        if tier == NON_D1:
            d2 = PITCHER_DIVISION_BENCHMARKS.get("D2", {})
            d3 = PITCHER_DIVISION_BENCHMARKS.get("D3", {})
            return _average_benchmarks(d2, d3)
        return PITCHER_DIVISION_BENCHMARKS.get(
            benchmark_key, PITCHER_DIVISION_BENCHMARKS.get("Non-P4 D1", {})
        )

    pos_benchmarks = get_position_benchmarks(player_position)
    if tier == NON_D1:
        d2 = pos_benchmarks.get("D2", {})
        d3 = pos_benchmarks.get("D3", {})
        return _average_benchmarks(d2, d3)
    return pos_benchmarks.get(
        benchmark_key, pos_benchmarks.get("Non-P4 D1", {})
    )


# ---------------------------------------------------------------------------
# Position-group z-score weights for hitter percentile calculation.
# Raw weights are normalized at runtime — only the ratios matter.
# Pitchers use equal weighting (no position-group variation).
# ---------------------------------------------------------------------------

_HITTER_Z_WEIGHTS: Dict[str, Dict[str, float]] = {
    "OF": {
        "exit_velo": 1.0,
        "sixty_time": 1.0,   # neutral — OF need balanced tools
        "of_velo": 1.0,
    },
    "MIF": {
        "exit_velo": 1.0,
        "sixty_time": 1.0,   # neutral — MIF need all tools
        "inf_velo": 1.0,
    },
    "CIF": {
        "exit_velo": 1.2,    # power matters more for corner guys
        "sixty_time": 0.6,   # slow 3B/1B is acceptable
        "inf_velo": 1.0,
    },
    "C": {
        "exit_velo": 1.0,
        "sixty_time": 1.0,
        "c_velo": 1.0,
        "pop_time": 1.0,
    },
}

_OF_POSITIONS = frozenset({"OF", "CF", "RF", "LF", "OUTFIELDER"})
_MIF_POSITIONS = frozenset({"SS", "2B", "MIF"})
_CIF_POSITIONS = frozenset({"3B", "1B"})
_C_POSITIONS = frozenset({"C", "CATCHER"})


def _hitter_position_group(player_position: str) -> str:
    pos = player_position.strip().upper() if player_position else ""
    if pos in _OF_POSITIONS:
        return "OF"
    if pos in _MIF_POSITIONS:
        return "MIF"
    if pos in _CIF_POSITIONS:
        return "CIF"
    if pos in _C_POSITIONS:
        return "C"
    return "MIF"


def compute_within_tier_percentile(
    player_stats: Dict[str, Any],
    predicted_tier: str,
    is_pitcher: bool,
    player_position: str = "",
) -> float:
    """
    Compute a within-tier percentile (0-100) by averaging stat z-scores against
    the benchmark means/stds for the predicted tier.

    For hitters, z-scores are weighted by position group so that the most
    recruitable tools for each position carry more influence.
    """
    tier = normalize_predicted_tier(predicted_tier)
    benchmarks = _resolve_tier_benchmarks_for_percentile(
        tier, is_pitcher, player_position,
    )

    if is_pitcher:
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

    # Compute z-scores with position-aware weighting for hitters.
    pos_group = _hitter_position_group(player_position) if not is_pitcher else ""
    z_weights = _HITTER_Z_WEIGHTS.get(pos_group, {})

    weighted_z_sum = 0.0
    total_weight = 0.0
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

        w = z_weights.get(stat_name, 1.0)
        weighted_z_sum += z * w
        total_weight += w

    if total_weight <= 0:
        return 50.0

    avg_z = weighted_z_sum / total_weight
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
    """Compute tier-aware player PCI from ML percentile + d1/p4 probability.

    Includes stat-based demotion: if a player's measurable metrics place them
    in the bottom of their predicted tier, the tier is demoted and the
    percentile recalculated against the lower tier's benchmarks. This catches
    cases where the ML model is confident but the stats don't support the call.
    """
    normalized_tier = normalize_predicted_tier(predicted_tier)
    player_position = player_stats.get("primary_position", "") or ""
    demotion_threshold = 15.0 if is_pitcher else 20.0

    within_tier_percentile = compute_within_tier_percentile(
        player_stats=player_stats,
        predicted_tier=normalized_tier,
        is_pitcher=is_pitcher,
        player_position=player_position,
    )

    # Stat-based demotion: if metrics place the player in the bottom of their
    # predicted tier, demote and recalculate against lower-tier benchmarks.
    # Demotion chain: P4 -> Non-P4 D1 -> Non-D1 (stops at Non-D1).
    _DEMOTION_CHAIN = {POWER_4_D1: NON_P4_D1, NON_P4_D1: NON_D1}
    next_tier = _DEMOTION_CHAIN.get(normalized_tier)
    while next_tier and within_tier_percentile < demotion_threshold:
        logger.info(
            "Stat-based demotion: %s -> %s (within_tier_pct=%.1f < %.1f)",
            normalized_tier,
            next_tier,
            within_tier_percentile,
            demotion_threshold,
        )
        normalized_tier = next_tier
        within_tier_percentile = compute_within_tier_percentile(
            player_stats=player_stats,
            predicted_tier=normalized_tier,
            is_pitcher=is_pitcher,
            player_position=player_position,
        )
        next_tier = _DEMOTION_CHAIN.get(normalized_tier)

    ml_pci = ml_based_pci(
        predicted_tier=normalized_tier,
        within_tier_percentile=within_tier_percentile,
        d1_prob=d1_probability,
        p4_prob=p4_probability,
    )

    player_pci_value = final_pci(ml_pci)

    return {
        "predicted_tier": normalized_tier,
        "within_tier_percentile": round(within_tier_percentile, 1),
        "ml_pci": round(ml_pci, 2),
        "player_pci": round(player_pci_value, 2),
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
        return "Fit"

    delta = player_academic_rating - school_academic_rating

    if delta > 2.0:
        return "Strong Safety"
    if delta > 0.6:
        return "Safety"
    if delta >= -0.6:
        return "Fit"
    if delta >= -1.5:
        return "Reach"
    if delta >= -2.0:
        return "Strong Reach"
    # Beyond strong reach — exclude
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
    ranking_priority: Optional[str] = None,
    selected_states: Optional[List[str]] = None,
    excluded_states: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Match schools against player PCI, apply filters, and return a balanced list.

    When ``consideration_pool=True``, the function returns a broader candidate
    set (wider delta range, relaxed exclusion rules) intended for downstream
    roster research that will perform final selection.

    ``ranking_priority`` ("academics" | "baseball_fit" | None) biases the
    consideration-pool sort so the candidate set honors the user's main
    preference before the LLM rerank runs. Without it, academically-perfect
    Strong-Safety-baseball schools get dropped at the gate and never reach
    the stage that could surface them.

    ``selected_states`` is a list of 2-letter state abbreviations that add
    to the region filter. The allowed geography is the UNION of states in
    ``selected_regions`` and ``selected_states``, minus any states in
    ``excluded_states`` — lets a user who wants all of Northeast except
    Maine explicitly subtract ME after selecting the region.
    """
    player_academic_rounded = academic_composite
    candidates: List[Dict[str, Any]] = []

    # Build the allowed-state set as union(states in selected regions,
    # explicitly selected states) - excluded_states. If neither regions nor
    # states are provided, no geo filter is applied.
    allowed_states: Optional[set] = None
    if selected_regions or selected_states:
        allowed_states = set()
        if selected_regions:
            for region in selected_regions:
                allowed_states.update(REGION_STATES.get(region, set()))
        if selected_states:
            for st in selected_states:
                if st:
                    allowed_states.add(st.strip().upper())
        if excluded_states:
            for st in excluded_states:
                if st:
                    allowed_states.discard(st.strip().upper())
        if not allowed_states:
            allowed_states = None

    # Hard academic floor when the user explicitly prioritizes academics:
    # exclude schools whose selectivity is more than 2.5 below the student's
    # effective academic composite. Applied at the gate (before the 50-school
    # consideration pool is built) so downstream bonus/penalty math only sees
    # schools that make academic sense. Missing-selectivity schools fall back
    # to 2.5, which will fail this filter for any student above ~5.0.
    academic_floor: Optional[float] = None
    if ranking_priority == "academics":
        academic_floor = float(academic_composite) - 2.5

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

        # Preference filter: academic floor (only when priority is academics)
        if academic_floor is not None:
            raw_sel = school.get("academic_selectivity_score")
            try:
                sel_for_floor = float(raw_sel) if raw_sel is not None else 2.5
            except (TypeError, ValueError):
                sel_for_floor = 2.5
            if sel_for_floor < academic_floor:
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

        # Fallback for schools missing an academic_selectivity_score. The
        # ~12-15 such schools in the DB are empirically low-selectivity
        # (unranked / open-enrollment / weak academic profile), so 2.5 is
        # closer to reality than a neutral default. Mirrors
        # _MISSING_SELECTIVITY_FALLBACK in ranking.py.
        school_selectivity = school.get("academic_selectivity_score")
        if school_selectivity is not None:
            try:
                school_acad_numeric: Optional[float] = float(school_selectivity)
            except (TypeError, ValueError):
                school_acad_numeric = 2.5
        else:
            school_acad_numeric = 2.5
        acad_label = _academic_fit_label(player_academic_rounded, school_acad_numeric)
        if acad_label is None:
            continue

        if not consideration_pool:
            # Exclude only extreme double-mismatches where the school is
            # a strong outlier in both dimensions.
            if fit_label == "Strong Safety" and acad_label in ("Strong Safety",):
                continue

        if consideration_pool:
            # Exclude schools that are settling in both dimensions:
            # baseball safety/strong-safety AND academic strong safety.
            if fit_label in ("Safety", "Strong Safety") and acad_label == "Strong Safety":
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
            "academic_selectivity_score": school_acad_numeric,
            "estimated_annual_cost": display_tuition,
            "metric_comparisons": metric_comparisons,
            "delta": round(delta, 2),
            "sci": round(float(school_sci), 2),
            "trend": f"{trend_bonus:+.2f}",
            "trend_bonus": round(trend_bonus, 2),
            "academic_delta": round(player_academic_rounded - (school_acad_numeric or 2.0), 2),
            "_abs_delta": abs(delta),
            # School general info for LLM context
            "school_city": school.get("school_city"),
            "undergrad_enrollment": school.get("undergrad_enrollment"),
            "overall_grade": school.get("overall_grade"),
            "academics_grade": school.get("academics_grade"),
            "campus_life_grade": school.get("campus_life_grade"),
            "student_life_grade": school.get("student_life_grade"),
            # Baseball record from rankings enrichment
            "baseball_record": school.get("baseball_record"),
            "baseball_wins": school.get("baseball_wins"),
            "baseball_losses": school.get("baseball_losses"),
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
        # Consideration pool: blend baseball closeness with academic fit
        # quality so academically appropriate schools surface alongside
        # pure baseball-fit matches.
        _ACAD_DISTANCE = {
            "Fit": 0.0, "Safety": 1.0, "Reach": 1.5,
            "Strong Safety": 3.0, "Strong Reach": 3.5,
        }
        # Sort weights are priority-aware so the pool reflects what the user
        # actually said they care about before the LLM rerank trims it.
        if ranking_priority == "academics":
            # Care less about baseball distance, more about academic fit.
            _ABS_DELTA_WEIGHT = 0.5
            _ACAD_WEIGHT = 3.0
            _MIN_ACAD_DIVERSE = 20
        elif ranking_priority == "baseball_fit":
            # Tight baseball targeting, academics secondary.
            _ABS_DELTA_WEIGHT = 1.3
            _ACAD_WEIGHT = 0.8
            _MIN_ACAD_DIVERSE = 8
        else:
            _ABS_DELTA_WEIGHT = 1.0
            _ACAD_WEIGHT = 1.5
            _MIN_ACAD_DIVERSE = 12

        candidates.sort(
            key=lambda x: x["_abs_delta"] * _ABS_DELTA_WEIGHT
            + _ACAD_DISTANCE.get(x.get("academic_fit", "Fit"), 2.0) * _ACAD_WEIGHT
        )

        # Reserve slots for academically appropriate schools so downstream
        # research has academic diversity to work with.
        acad_good = [
            c for c in candidates
            if c.get("academic_fit") in ("Fit", "Reach", "Safety")
        ]
        selected: List[Dict[str, Any]] = acad_good[:_MIN_ACAD_DIVERSE]
        selected_names = {s["school_name"] for s in selected}

        for c in candidates:
            if len(selected) >= limit:
                break
            if c["school_name"] not in selected_names:
                selected.append(c)
                selected_names.add(c["school_name"])

        selected = selected[:limit]
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
        player_position = player_stats.get("primary_position", "") or ""
        pos_benchmarks = get_position_benchmarks(player_position)
        benchmarks = pos_benchmarks.get(benchmark_key, {})
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
            decimals = 2 if unit == "sec" else 1
            player_num = round(float(player_val), decimals)
            bench_num = round(float(bench["mean"]), decimals)
        except (TypeError, ValueError, KeyError):
            continue

        comparisons.append({
            "metric": display_name,
            "player_value": player_num,
            "division_avg": bench_num,
            "unit": unit,
        })

    return comparisons
