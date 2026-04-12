"""
Competitiveness scoring primitives for BaseballPath matching.

SCI (School Competitiveness Index) and PCI (Player Competitiveness Index) are
both expressed on the same 0-100 national competitiveness scale.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend.constants import DIVISION_BENCHMARKS, PITCHER_DIVISION_BENCHMARKS, get_position_benchmarks
from backend.utils.position_tracks import primary_position_to_hitter_bucket
from backend.utils.school_group_constants import NON_D1, NON_P4_D1, POWER_4_D1

# ---------------------------------------------------------------------------
# SCI constants
# ---------------------------------------------------------------------------

DEFAULT_DIVISION_MAX_RANKS: Dict[str, float] = {
    "1": 305.0,
    "2": 253.0,
    "3": 388.0,
}

NATIONAL_BANDS: Dict[str, Tuple[float, float]] = {
    "1": (40.0, 100.0),
    "2": (10.0, 43.0),
    "3": (0.0, 38.0),
}

YEAR_WEIGHTS: Dict[str, float] = {
    "2025": 0.50,
    "2024": 0.30,
    "2023": 0.20,
}

SCI_METRIC_KEYS: Tuple[str, ...] = (
    "overall_rating",
    "offensive_rating",
    "defensive_rating",
    "power_rating",
)

# ---------------------------------------------------------------------------
# PCI constants
# ---------------------------------------------------------------------------

TIER_PCI_BANDS: Dict[str, Tuple[float, float]] = {
    POWER_4_D1: (65.0, 100.0),
    NON_P4_D1: (30.0, 72.0),
    NON_D1: (0.0, 40.0),
}

BENCHMARK_ANCHORS: Dict[str, float] = {
    "P4": 88.0,
    "Mid-Major D1": 62.0,
    "Low-Major D1": 47.0,
    "D2": 28.0,
    "D3": 15.0,
}

ML_TIER_TO_BENCHMARK: Dict[str, str] = {
    POWER_4_D1: "P4",
    NON_P4_D1: "Mid-Major D1",
    NON_D1: "Non D1",
}

HITTER_WEIGHT_TIERS: List[float] = [0.36, 0.34, 0.32]


def _gentle_descending_weights(metric_count: int, spread: float = 0.12) -> List[float]:
    """
    Generate lightly descending raw weights so better tools still lead without
    dominating the rest of the profile.
    """
    if metric_count <= 0:
        return []
    if metric_count == 1:
        return [1.0]

    high = 1.0 + (spread / 2.0)
    low = 1.0 - (spread / 2.0)
    step = (high - low) / float(metric_count - 1)
    return [high - (step * idx) for idx in range(metric_count)]


PITCHER_WEIGHT_TIERS_BY_COUNT: Dict[int, List[float]] = {
    count: _gentle_descending_weights(count)
    for count in range(2, 10)
}

LOWER_IS_BETTER = {"sixty_time", "pop_time"}

HITTER_POSITION_METRICS: Dict[str, List[Tuple[str, str]]] = {
    "IF": [("exit_velo", "exit_velo_max"), ("inf_velo", "inf_velo"), ("sixty_time", "sixty_time")],
    "OF": [("exit_velo", "exit_velo_max"), ("of_velo", "of_velo"), ("sixty_time", "sixty_time")],
    "C": [("exit_velo", "exit_velo_max"), ("c_velo", "c_velo"), ("pop_time", "pop_time")],
}

PITCHER_METRIC_MAP: List[Tuple[str, str]] = [
    ("FastballVelo Range", "fastball_velo_range"),
    ("FastballVelocity (max)", "fastball_velo_max"),
    ("FastballSpin Rate (avg)", "fastball_spin"),
    ("Changeup Velo Range", "changeup_velo"),
    ("Changeup Spin Rate (avg)", "changeup_spin"),
    ("Curveball Velo Range", "curveball_velo"),
    ("Curveball Spin Rate (avg)", "curveball_spin"),
    ("Slider Velo Range", "slider_velo"),
    ("Slider Spin Rate (avg)", "slider_spin"),
]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _normalize_year_key(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        year = int(value)
        if year <= 0:
            return None
        return str(year)
    except (TypeError, ValueError):
        return None


def _normalize_division_key(value: Any) -> Optional[str]:
    if value is None:
        return None

    try:
        division = int(value)
        if division in (1, 2, 3):
            return str(division)
    except (TypeError, ValueError):
        pass

    text = str(value).strip().lower()
    if not text:
        return None
    if "1" in text or "i" in text and "ii" not in text and "iii" not in text:
        return "1"
    if "2" in text or "ii" in text:
        return "2"
    if "3" in text or "iii" in text:
        return "3"
    return None


def normalize_predicted_tier(value: Any) -> str:
    if not value:
        return NON_P4_D1

    lowered = str(value).strip().lower()
    if "power" in lowered and "4" in lowered:
        return POWER_4_D1
    if "non-p4" in lowered or "non p4" in lowered:
        return NON_P4_D1
    if "non-d1" in lowered or "non d1" in lowered or lowered in {"d2", "d3"}:
        return NON_D1
    return str(value).strip()


def normalize_hitter_position(value: Any) -> str:
    return primary_position_to_hitter_bucket(value)


def rank_to_percentile(rank: Any, max_rank_for_division: Any) -> Optional[float]:
    """Convert a rank (1=best) to percentile (100=best)."""
    try:
        rank_f = float(rank)
        max_rank_f = float(max_rank_for_division)
    except (TypeError, ValueError):
        return None

    if max_rank_f <= 1:
        return None

    percentile = (1.0 - ((rank_f - 1.0) / (max_rank_f - 1.0))) * 100.0
    return _clamp(percentile, 0.0, 100.0)


def to_national_scale(within_div_percentile: Any, division: Any) -> Optional[float]:
    division_key = _normalize_division_key(division)
    if division_key is None:
        return None

    band = NATIONAL_BANDS.get(division_key)
    if band is None:
        return None

    try:
        percentile = float(within_div_percentile)
    except (TypeError, ValueError):
        return None

    low, high = band
    national = low + (_clamp(percentile, 0.0, 100.0) / 100.0) * (high - low)
    return _clamp(national, 0.0, 100.0)


def recency_weighted(values_by_year: Dict[str, Optional[float]]) -> Optional[float]:
    available: Dict[str, float] = {}
    for year, value in values_by_year.items():
        if value is None:
            continue
        if year not in YEAR_WEIGHTS:
            continue
        available[year] = float(value)

    if not available:
        return None

    total_weight = sum(YEAR_WEIGHTS[y] for y in available)
    if total_weight <= 0:
        return None

    weighted_sum = sum(available[y] * YEAR_WEIGHTS[y] for y in available)
    return weighted_sum / total_weight


def compute_trend_bonus(sci_by_year: Dict[str, Optional[float]]) -> float:
    """Compute a bounded trend bonus in [-5, +5]."""
    if sci_by_year.get("2025") is None:
        return 0.0

    sci_2025 = float(sci_by_year["2025"])
    sci_2024 = float(sci_by_year.get("2024", sci_2025) or sci_2025)
    sci_2023 = float(sci_by_year.get("2023", sci_2025) or sci_2025)

    trend_1yr = sci_2025 - sci_2024
    trend_2yr = sci_2025 - sci_2023
    raw = (0.6 * trend_1yr) + (0.4 * trend_2yr)
    return _clamp(raw * 0.15, -5.0, 5.0)


def _resolve_max_rank(
    *,
    year: str,
    division: str,
    metric_key: str,
    max_ranks_by_year_div_metric: Optional[Dict[Tuple[str, str, str], float]] = None,
) -> Optional[float]:
    default_rank = DEFAULT_DIVISION_MAX_RANKS.get(division)

    if max_ranks_by_year_div_metric:
        metric_specific = max_ranks_by_year_div_metric.get((year, division, metric_key))
        if metric_specific and metric_specific > 1:
            if default_rank and default_rank > 1:
                return float(max(metric_specific, default_rank))
            return float(metric_specific)
        metric_fallback = max_ranks_by_year_div_metric.get((year, division, "overall_rating"))
        if metric_fallback and metric_fallback > 1:
            if default_rank and default_rank > 1:
                return float(max(metric_fallback, default_rank))
            return float(metric_fallback)

    if default_rank and default_rank > 1:
        return default_rank
    return None


def _blend_weighted_components(
    weighted_components: Dict[str, Optional[float]],
    weights: Dict[str, float],
) -> Optional[float]:
    numerator = 0.0
    denominator = 0.0

    for key, weight in weights.items():
        value = weighted_components.get(key)
        if value is None:
            continue
        numerator += float(value) * weight
        denominator += weight

    if denominator <= 0:
        return None
    return numerator / denominator


def compute_school_sci_from_rankings(
    rankings_by_year: Dict[Any, Dict[str, Any]],
    max_ranks_by_year_div_metric: Optional[Dict[Tuple[str, str, str], float]] = None,
) -> Dict[str, Any]:
    """
    Compute SCI for a school from yearly Massey ranking rows.

    `rankings_by_year` should contain rows keyed by year (e.g., 2025/2024/2023),
    with each row including `division` and rank fields in `SCI_METRIC_KEYS`.
    """
    yearly_metric_scores: Dict[str, Dict[str, Optional[float]]] = {
        metric: {} for metric in SCI_METRIC_KEYS
    }

    for year in YEAR_WEIGHTS:
        row = rankings_by_year.get(year)
        if row is None:
            # Also handle integer-year dictionary keys.
            try:
                row = rankings_by_year.get(int(year))
            except (TypeError, ValueError):
                row = None
        if row is None:
            for metric in SCI_METRIC_KEYS:
                yearly_metric_scores[metric][year] = None
            continue

        division = _normalize_division_key(row.get("division"))
        if division is None:
            for metric in SCI_METRIC_KEYS:
                yearly_metric_scores[metric][year] = None
            continue

        for metric in SCI_METRIC_KEYS:
            max_rank = _resolve_max_rank(
                year=year,
                division=division,
                metric_key=metric,
                max_ranks_by_year_div_metric=max_ranks_by_year_div_metric,
            )
            if max_rank is None:
                yearly_metric_scores[metric][year] = None
                continue
            percentile = rank_to_percentile(row.get(metric), max_rank)
            national = to_national_scale(percentile, division)
            yearly_metric_scores[metric][year] = national

    weighted_components: Dict[str, Optional[float]] = {
        "overall_weighted": recency_weighted(yearly_metric_scores["overall_rating"]),
        "offensive_weighted": recency_weighted(yearly_metric_scores["offensive_rating"]),
        "defensive_weighted": recency_weighted(yearly_metric_scores["defensive_rating"]),
        "power_weighted": recency_weighted(yearly_metric_scores["power_rating"]),
    }

    trend_bonus = compute_trend_bonus(yearly_metric_scores["overall_rating"])

    hitter_base = _blend_weighted_components(
        weighted_components,
        {
            "overall_weighted": 0.50,
            "offensive_weighted": 0.35,
            "power_weighted": 0.15,
        },
    )
    pitcher_base = _blend_weighted_components(
        weighted_components,
        {
            "overall_weighted": 0.50,
            "power_weighted": 0.30,
            "defensive_weighted": 0.20,
        },
    )

    sci_hitter = None
    if hitter_base is not None:
        sci_hitter = _clamp(hitter_base + trend_bonus, 0.0, 100.0)

    sci_pitcher = None
    if pitcher_base is not None:
        sci_pitcher = _clamp(pitcher_base + trend_bonus, 0.0, 100.0)

    return {
        "overall_weighted": weighted_components["overall_weighted"],
        "offensive_weighted": weighted_components["offensive_weighted"],
        "defensive_weighted": weighted_components["defensive_weighted"],
        "power_weighted": weighted_components["power_weighted"],
        "trend_bonus": trend_bonus,
        "sci_hitter": sci_hitter,
        "sci_pitcher": sci_pitcher,
        "yearly_overall_national": yearly_metric_scores["overall_rating"],
    }


def ml_based_pci(
    predicted_tier: str,
    within_tier_percentile: float,
    d1_prob: Optional[float],
    p4_prob: Optional[float],
) -> float:
    tier = normalize_predicted_tier(predicted_tier)
    low, high = TIER_PCI_BANDS.get(tier, TIER_PCI_BANDS[NON_P4_D1])

    percentile = _clamp(float(within_tier_percentile), 0.0, 100.0)
    base = low + (percentile / 100.0) * (high - low)

    if tier == POWER_4_D1 and p4_prob is not None:
        base += (float(p4_prob) - 0.65) * 8.0
    elif tier == NON_P4_D1 and d1_prob is not None:
        base += (float(d1_prob) - 0.65) * 6.0
    elif tier == NON_D1 and d1_prob is not None:
        # Non-D1 players still get a light adjustment for how close they are
        # to the D1 cutoff, but the effect is intentionally small.
        base += (float(d1_prob) - 0.25) * 4.0

    return _clamp(base, 0.0, 100.0)


def interpolate(val: float, anchors: Sequence[Tuple[float, float]], lower_is_better: bool) -> Optional[float]:
    """
    Linearly interpolate a value across anchor points on national scale.

    `anchors` are `(benchmark_value, national_anchor)` pairs.
    """
    if len(anchors) < 2:
        return None

    sorted_anchors = sorted(anchors, key=lambda item: item[0], reverse=lower_is_better)

    for i in range(len(sorted_anchors) - 1):
        bm_a, ns_a = sorted_anchors[i]
        bm_b, ns_b = sorted_anchors[i + 1]

        if lower_is_better:
            # Descending benchmarks: high=worst, low=best
            bm_high, bm_low = bm_a, bm_b
            if bm_low <= val <= bm_high:
                denom = bm_high - bm_low
                t = (bm_high - val) / denom if denom else 0.5
                return ns_a + t * (ns_b - ns_a)
        else:
            bm_low, bm_high = bm_a, bm_b
            if bm_low <= val <= bm_high:
                denom = bm_high - bm_low
                t = (val - bm_low) / denom if denom else 0.5
                return ns_a + t * (ns_b - ns_a)

    # Extrapolate with a small bounded extension for exceptional outliers.
    if lower_is_better:
        worst_bm, worst_ns = sorted_anchors[0]
        best_bm, best_ns = sorted_anchors[-1]
        if val < best_bm:
            return _clamp(best_ns + 5.0, 0.0, 105.0)
        if val > worst_bm:
            return _clamp(worst_ns - 5.0, 0.0, 105.0)
    else:
        lowest_bm, lowest_ns = sorted_anchors[0]
        highest_bm, highest_ns = sorted_anchors[-1]
        if val > highest_bm:
            return _clamp(highest_ns + 5.0, 0.0, 105.0)
        if val < lowest_bm:
            return _clamp(lowest_ns - 5.0, 0.0, 105.0)

    return None


def _resolve_tier_benchmarks(
    benchmarks: Dict[str, Dict[str, Dict[str, float]]],
    tier: str,
) -> Dict[str, Dict[str, float]]:
    aliases = {
        "P4": ["P4"],
        "Mid-Major D1": ["Mid-Major D1", "Mid Major D1"],
        "Low-Major D1": ["Low-Major D1", "Low Major D1"],
        "Non D1": ["Non D1", "Non-D1"],
        "D2": ["D2"],
        "D3": ["D3"],
        "Non-P4 D1": ["Non-P4 D1", "Non P4 D1"],
    }
    for key in aliases.get(tier, [tier]):
        if key in benchmarks:
            return benchmarks[key]
    return {}


def _metric_national_score(
    *,
    benchmarks: Dict[str, Dict[str, Dict[str, float]]],
    benchmark_metric_key: str,
    player_value: float,
    lower_is_better: bool,
) -> Optional[float]:
    anchors: List[Tuple[float, float]] = []
    for tier, national_anchor in BENCHMARK_ANCHORS.items():
        tier_bench = _resolve_tier_benchmarks(benchmarks, tier)
        bm_entry = tier_bench.get(benchmark_metric_key)
        if not bm_entry:
            continue
        mean = bm_entry.get("mean")
        if mean is None:
            continue
        anchors.append((float(mean), float(national_anchor)))

    if len(anchors) < 2:
        return None

    return interpolate(float(player_value), anchors, lower_is_better=lower_is_better)


def _pct_deviation(player_value: float, benchmark_value: Optional[float], lower_is_better: bool) -> float:
    if benchmark_value is None:
        return 0.0
    if benchmark_value == 0:
        return 0.0
    if lower_is_better:
        return ((benchmark_value - player_value) / benchmark_value) * 100.0
    return ((player_value - benchmark_value) / benchmark_value) * 100.0


def _build_hitter_metric_inputs(
    player_metrics: Dict[str, Any],
    player_position: str,
) -> List[Tuple[str, float]]:
    metric_pairs = HITTER_POSITION_METRICS[normalize_hitter_position(player_position)]
    result: List[Tuple[str, float]] = []

    for benchmark_key, player_key in metric_pairs:
        raw_val = player_metrics.get(player_key)
        if raw_val is None and benchmark_key == "exit_velo":
            raw_val = player_metrics.get("exit_velo")
        if raw_val is None:
            continue
        try:
            result.append((benchmark_key, float(raw_val)))
        except (TypeError, ValueError):
            continue
    return result


def _hitter_benchmark_pci(
    player_metrics: Dict[str, Any],
    player_position: str,
    predicted_tier: str,
    benchmarks: Dict[str, Dict[str, Dict[str, float]]],
) -> Optional[float]:
    metric_values = _build_hitter_metric_inputs(player_metrics, player_position)
    if not metric_values:
        return None

    predicted_benchmark_tier = ML_TIER_TO_BENCHMARK.get(normalize_predicted_tier(predicted_tier), "Mid-Major D1")
    predicted_benchmarks = _resolve_tier_benchmarks(benchmarks, predicted_benchmark_tier)

    metric_scores: Dict[str, float] = {}
    metric_strength: Dict[str, float] = {}
    for metric_key, player_value in metric_values:
        lower_is_better = metric_key in LOWER_IS_BETTER
        score = _metric_national_score(
            benchmarks=benchmarks,
            benchmark_metric_key=metric_key,
            player_value=player_value,
            lower_is_better=lower_is_better,
        )
        if score is None:
            continue

        metric_scores[metric_key] = score
        benchmark_entry = predicted_benchmarks.get(metric_key) or {}
        benchmark_mean = benchmark_entry.get("mean")
        metric_strength[metric_key] = _pct_deviation(player_value, benchmark_mean, lower_is_better)

    if not metric_scores:
        return None

    available_metrics = list(metric_scores.keys())
    if len(available_metrics) < 3:
        equal_weight = 1.0 / len(available_metrics)
        return _clamp(
            sum(metric_scores[m] * equal_weight for m in available_metrics),
            0.0,
            100.0,
        )

    ranked = sorted(
        available_metrics,
        key=lambda metric: (metric_strength.get(metric, 0.0), metric_scores[metric]),
        reverse=True,
    )[:3]

    weighted_sum = 0.0
    total_weight = 0.0
    for metric, weight in zip(ranked, HITTER_WEIGHT_TIERS):
        weighted_sum += metric_scores[metric] * weight
        total_weight += weight

    if total_weight <= 0:
        return None
    return _clamp(weighted_sum / total_weight, 0.0, 100.0)


def _pitcher_benchmark_pci(
    player_metrics: Dict[str, Any],
    predicted_tier: str,
    benchmarks: Dict[str, Dict[str, Dict[str, float]]],
) -> Optional[float]:
    predicted_benchmark_tier = ML_TIER_TO_BENCHMARK.get(normalize_predicted_tier(predicted_tier), "Mid-Major D1")
    predicted_benchmarks = _resolve_tier_benchmarks(benchmarks, predicted_benchmark_tier)

    metric_scores: Dict[str, float] = {}
    metric_strength: Dict[str, float] = {}

    for benchmark_key, player_key in PITCHER_METRIC_MAP:
        raw_val = player_metrics.get(player_key)
        if raw_val is None:
            continue

        try:
            player_value = float(raw_val)
        except (TypeError, ValueError):
            continue

        score = _metric_national_score(
            benchmarks=benchmarks,
            benchmark_metric_key=benchmark_key,
            player_value=player_value,
            lower_is_better=False,
        )
        if score is None:
            continue

        metric_scores[benchmark_key] = score
        benchmark_entry = predicted_benchmarks.get(benchmark_key) or {}
        benchmark_mean = benchmark_entry.get("mean")
        metric_strength[benchmark_key] = _pct_deviation(player_value, benchmark_mean, lower_is_better=False)

    if not metric_scores:
        return None

    metric_count = len(metric_scores)
    if metric_count == 1:
        only_metric = next(iter(metric_scores.values()))
        return _clamp(only_metric, 0.0, 100.0)

    weights = PITCHER_WEIGHT_TIERS_BY_COUNT.get(metric_count)
    if not weights:
        # Fallback for unexpected counts: descending linear weights.
        descending = list(range(metric_count, 0, -1))
        total = sum(descending)
        weights = [value / total for value in descending]

    ranked = sorted(
        metric_scores.keys(),
        key=lambda metric: (metric_strength.get(metric, 0.0), metric_scores[metric]),
        reverse=True,
    )

    weighted_sum = 0.0
    total_weight = 0.0
    for metric, weight in zip(ranked, weights):
        weighted_sum += metric_scores[metric] * weight
        total_weight += weight

    if total_weight <= 0:
        return None

    return _clamp(weighted_sum / total_weight, 0.0, 100.0)


def benchmark_pci(
    player_metrics: Dict[str, Any],
    player_type: str,
    player_position: str,
    predicted_tier: str,
    benchmarks: Optional[Dict[str, Dict[str, Dict[str, float]]]] = None,
) -> Optional[float]:
    """
    Compute benchmark-based PCI from raw player metrics.
    """
    if player_type == "pitcher":
        benchmark_dict = benchmarks or PITCHER_DIVISION_BENCHMARKS
        return _pitcher_benchmark_pci(
            player_metrics=player_metrics,
            predicted_tier=predicted_tier,
            benchmarks=benchmark_dict,
        )

    benchmark_dict = benchmarks or get_position_benchmarks(player_position)
    return _hitter_benchmark_pci(
        player_metrics=player_metrics,
        player_position=player_position,
        predicted_tier=predicted_tier,
        benchmarks=benchmark_dict,
    )


def final_pci(ml_pci: float, benchmark_pci_value: Optional[float]) -> float:
    if benchmark_pci_value is None:
        return _clamp(float(ml_pci), 0.0, 100.0)
    return _clamp((0.60 * float(ml_pci)) + (0.40 * float(benchmark_pci_value)), 0.0, 100.0)


def compute_fit_delta(player_pci: float, school_sci: float) -> float:
    return float(player_pci) - float(school_sci)


def classify_fit(delta: float) -> str:
    if delta > 8:
        return "Strong Safety"
    if delta > 4:
        return "Safety"
    if delta >= -4:
        return "Fit"
    if delta >= -8:
        return "Reach"
    return "Strong Reach"


def to_legacy_fit_label(fit_label: str) -> str:
    lowered = fit_label.strip().lower()
    if "safety" in lowered:
        return "safety"
    if "reach" in lowered:
        return "reach"
    return "fit"
