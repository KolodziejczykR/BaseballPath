"""Deterministic talking-points extractor for the school review prompt.

Picks 2-4 ranked talking points per school + player so the LLM is forced to
*lead* with the most distinctive thing about that specific school instead of
defaulting to brochure-speak. Pure function; called once per school in
``service.py`` before ``review_school`` and passed into the LLM payload.

The thresholds (±15% for "stands out", within ±10% for "in line") are encoded
once here so prompt and code stay consistent.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.constants import PITCHER_DIVISION_BENCHMARKS, get_position_benchmarks

from .evidence import _safe_int
from .types import GatheredEvidence


def _stable_index(key: str, num_variants: int) -> int:
    """Deterministic index in [0, num_variants) keyed off a string.

    Used to pick a surface-form variant for talking-point fact text so the
    same school always produces the same phrasing (testable, predictable)
    while different schools rotate through different variants. Avoids the
    failure mode where every school's writeup opens "[N] of [M] projected
    pitchers..." because the talking_point text is identical.
    """
    if num_variants <= 1:
        return 0
    h = hashlib.md5(key.encode("utf-8")).hexdigest()
    return int(h[:8], 16) % num_variants


def _spell_small(n: int) -> str:
    """Spell 0-9 as words ('Three of the 19...') for prose feel; digits otherwise."""
    words = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
    return words[n] if 0 <= n <= 9 else str(n)


# ±15% of the division mean is the "stands out" threshold. Within ±10% is
# "in line". Below that is a gap and is intentionally NOT surfaced — players
# don't need to be reminded of weaknesses in a recommendation.
STANDOUT_RELATIVE_DELTA = 0.15
IN_LINE_RELATIVE_DELTA = 0.10

# Pitcher metrics: (display, player_key, benchmark_key, direction).
# direction = +1 means higher player value is better (e.g. fastball velo,
# breaking-ball spin). direction = -1 means lower is better — for a changeup,
# we want big velocity separation off the fastball *and* lower spin to get
# more fade, so both changeup_velo and changeup_spin are inverted.
_PITCHER_METRICS = [
    ("fastball velocity",  "fastball_velo_max", "FastballVelocity (max)",     +1),
    ("fastball spin",      "fastball_spin",     "FastballSpin Rate (avg)",    +1),
    ("changeup velocity",  "changeup_velo",     "Changeup Velo Range",        -1),
    ("changeup spin",      "changeup_spin",     "Changeup Spin Rate (avg)",   -1),
    ("curveball velocity", "curveball_velo",    "Curveball Velo Range",       +1),
    ("curveball spin",     "curveball_spin",    "Curveball Spin Rate (avg)",  +1),
    ("slider velocity",    "slider_velo",       "Slider Velo Range",          +1),
    ("slider spin",        "slider_spin",       "Slider Spin Rate (avg)",     +1),
]

# Hitter base metrics; position-conditional throwing metrics are appended
# inside _build_hitter_comparisons.
_HITTER_BASE_METRICS = [
    ("exit velocity", "exit_velo_max", "exit_velo",  +1),
    ("60-yard time",  "sixty_time",    "sixty_time", -1),
]

# Mirrors backend.evaluation.school_matching.TIER_TO_BENCHMARK_KEY, inlined
# here to avoid pulling that whole module into the deep_school_insights import
# graph. KEEP IN SYNC: PITCHER_DIVISION_BENCHMARKS uses "P4" as the Power-4
# key; the user-facing division_group string is "Power 4 D1". Returning
# "Power 4 D1" silently misses the lookup — every Power-4 school would
# produce zero metric standouts (caught when reviewing run f41e3b71).
_TIER_TO_BENCHMARK_KEY = {
    "Power 4 D1": "P4",
    "Non-P4 D1": "Non-P4 D1",
}


@dataclass
class TalkingPoint:
    kind: str       # "metric_standout" | "roster_opportunity" | "academic_angle" | "level_descriptor"
    priority: int   # lower = more important. Used to sort before passing to the LLM.
    fact: str       # one-clause description for the LLM to weave into prose


def format_division_label(division_group: str, division: Any) -> str:
    """Resolve the player-facing label for a school's level.

    Power 4 D1   → "Power Four Division I"
    Non-P4 D1    → "Mid-Major Division I"
    Non-D1 + 2   → "Division II"
    Non-D1 + 3   → "Division III"
    Non-D1 else  → "NAIA"  (placeholder until NAIA records exist)
    """
    g = (division_group or "").strip()
    if g == "Power 4 D1":
        return "Power Four Division I"
    if g == "Non-P4 D1":
        return "Mid-Major Division I"
    if g == "Non-D1":
        try:
            d = int(float(division))
        except (TypeError, ValueError):
            d = None
        if d == 2:
            return "Division II"
        if d == 3:
            return "Division III"
        return "NAIA"
    return g  # unknown bucket — pass through unchanged


def _resolve_benchmark_key(division_group: str, division: Any) -> str:
    if (division_group or "").strip() == "Non-D1":
        try:
            d = int(float(division))
        except (TypeError, ValueError):
            d = None
        if d == 2:
            return "D2"
        if d == 3:
            return "D3"
        # Non-D1 with no division match (NAIA placeholder or missing).
        # The benchmark table has no "Non D1" key, so fall back to D2 —
        # the closest meaningful level — instead of silently dropping
        # the lookup.
        return "D2"
    return _TIER_TO_BENCHMARK_KEY.get(division_group, "Non-P4 D1")


def _signed_relative_delta(player: float, bench: float, direction: int) -> Optional[float]:
    """Return a signed relative delta where positive = standout direction.

    For +1 metrics, positive = player above the average (good).
    For -1 metrics, positive = player below the average (also good — faster 60,
    slower changeup, etc.).
    """
    if bench == 0:
        return None
    raw = (player - bench) / bench
    return raw if direction > 0 else -raw


def _build_pitcher_comparisons(
    school: Dict[str, Any], player_stats: Dict[str, Any]
) -> List[Dict[str, Any]]:
    key = _resolve_benchmark_key(
        school.get("division_group") or "",
        school.get("baseball_division") or school.get("division"),
    )
    bench_table = PITCHER_DIVISION_BENCHMARKS.get(key, {})
    out: List[Dict[str, Any]] = []
    for display, p_key, b_key, direction in _PITCHER_METRICS:
        p_val = player_stats.get(p_key)
        bench = bench_table.get(b_key)
        if p_val is None or not bench:
            continue
        try:
            p_num = float(p_val)
            b_num = float(bench["mean"])
        except (TypeError, ValueError, KeyError):
            continue
        rel = _signed_relative_delta(p_num, b_num, direction)
        if rel is None:
            continue
        out.append({"display": display, "rel_delta": rel})
    return out


def _build_hitter_comparisons(
    school: Dict[str, Any], player_stats: Dict[str, Any]
) -> List[Dict[str, Any]]:
    pos = (player_stats.get("primary_position") or "").strip().upper()
    pos_benchmarks = get_position_benchmarks(pos)
    key = _resolve_benchmark_key(
        school.get("division_group") or "",
        school.get("baseball_division") or school.get("division"),
    )
    bench_table = pos_benchmarks.get(key, {})

    metrics = list(_HITTER_BASE_METRICS)
    if pos in {"OF", "LF", "CF", "RF"} and player_stats.get("of_velo") is not None:
        metrics.append(("outfield throwing velocity", "of_velo", "of_velo", +1))
    elif pos in {"SS", "2B", "3B", "1B", "MI"} and player_stats.get("inf_velo") is not None:
        metrics.append(("infield throwing velocity", "inf_velo", "inf_velo", +1))
    elif pos in {"C", "CATCHER"}:
        if player_stats.get("c_velo") is not None:
            metrics.append(("catcher throwing velocity", "c_velo", "c_velo", +1))
        if player_stats.get("pop_time") is not None:
            metrics.append(("pop time", "pop_time", "pop_time", -1))

    out: List[Dict[str, Any]] = []
    for display, p_key, b_key, direction in metrics:
        p_val = player_stats.get(p_key)
        bench = bench_table.get(b_key)
        if p_val is None or not bench:
            continue
        try:
            p_num = float(p_val)
            b_num = float(bench["mean"])
        except (TypeError, ValueError, KeyError):
            continue
        rel = _signed_relative_delta(p_num, b_num, direction)
        if rel is None:
            continue
        out.append({"display": display, "rel_delta": rel})
    return out


def _metric_standout_points(
    school: Dict[str, Any],
    player_stats: Dict[str, Any],
    is_pitcher: bool,
) -> List[TalkingPoint]:
    comps = (
        _build_pitcher_comparisons(school, player_stats)
        if is_pitcher
        else _build_hitter_comparisons(school, player_stats)
    )
    standouts = [c for c in comps if c["rel_delta"] >= STANDOUT_RELATIVE_DELTA]
    standouts.sort(key=lambda c: -c["rel_delta"])

    points: List[TalkingPoint] = []
    # Cap at 3 standouts. Any more and the narrative starts listing instead
    # of telling a story.
    for i, c in enumerate(standouts[:3]):
        points.append(TalkingPoint(
            kind="metric_standout",
            priority=i,
            fact=(
                f"the player's {c['display']} stands out at this level — "
                f"well above what most projected recruits bring"
            ),
        ))
    return points


def _strong_signal_fact(school_name: str, same_family: int, departures: int, high_usage: int) -> str:
    """Strong-signal roster opportunity: 4 surface forms, rotated by school.

    Triggered when departures >= 3 AND returning_high_usage <= 2. Each variant
    explicitly explains that the non-departing returners are mostly depth /
    underclassmen who haven't claimed real innings — so a roster that looks
    "full" on paper (e.g. Marshall: 19 pitchers, 4 graduating, 15 returning)
    correctly reads as a real opportunity rather than inflated math, because
    only 1 of last year's high-usage arms is back.
    """
    d = _spell_small(departures)
    h = _spell_small(high_usage)
    sf = _spell_small(same_family)
    variants = [
        # 0: lead with the high-usage gap, explain depth nuance
        (
            f"Most of last year's high-usage arms are gone. {h.capitalize()} "
            f"returns from that group, and {d} more pitchers graduate from "
            f"this {sf}-pitcher staff. Meaningful innings will need to be "
            f"reassigned even though the roster looks full on paper."
        ),
        # 1: lead with senior turnover, explain depth nuance
        (
            f"{d.capitalize()} seniors graduate from this {sf}-pitcher staff, "
            f"and only {h} of last year's high-usage arms is back. The other "
            f"returners are depth pieces and underclassmen who haven't claimed "
            f"real innings yet."
        ),
        # 2: lead with what's open, no headcount math first
        (
            f"The rotation and bullpen need rebuilding here. Only {h} of last "
            f"year's high-usage arms returns, and {d} more pitchers graduate, "
            f"so meaningful innings are wide open even with {sf} pitchers on "
            f"the projected roster."
        ),
        # 3: lead with the working-arm math
        (
            f"This staff carries {sf} projected pitchers, but only {h} of them "
            f"put up meaningful innings last year. {d.capitalize()} seniors "
            f"leave, and the rest of the workload is open for whoever earns it."
        ),
    ]
    return variants[_stable_index(school_name, len(variants))]


def _moderate_signal_fact(school_name: str, same_family: int, departures: int) -> str:
    """Moderate-signal roster opportunity: 3 surface forms, rotated by school."""
    d = _spell_small(departures)
    sf = _spell_small(same_family)
    variants = [
        (
            f"{d.capitalize()} of the {sf} projected pitchers are seniors "
            f"graduating, so the position group churns enough next year to "
            f"open a realistic path to playing time."
        ),
        (
            f"This pitching group turns over {d} seniors out of {sf} arms next "
            f"year. The path to meaningful innings is real for someone who can "
            f"earn the trust early."
        ),
        (
            f"{d.capitalize()} seniors leave a {sf}-pitcher staff, which opens "
            f"real lanes behind the returning core for arms who can step into "
            f"a role."
        ),
    ]
    return variants[_stable_index(school_name, len(variants))]


def _crowded_signal_fact(school_name: str, returning_high_usage: int, departures: int) -> str:
    """Crowded-signal roster: 3 surface forms, rotated by school."""
    h = _spell_small(returning_high_usage)
    d = _spell_small(departures)
    variants = [
        (
            f"This is a settled staff. {h.capitalize()} high-usage pitchers "
            f"return and only {d} graduates, so earning innings here means "
            f"displacing established arms."
        ),
        (
            f"The pitching group is mostly intact next year. {h.capitalize()} "
            f"returning starters carried meaningful innings last season, and "
            f"only {d} pitcher leaves the group, so a freshman would compete "
            f"with an experienced staff."
        ),
        (
            f"Competition for innings will be real. The staff returns {h} "
            f"pitchers who put up significant work last year, with only {d} "
            f"departure, so meaningful reps will be hard to come by early."
        ),
    ]
    return variants[_stable_index(school_name, len(variants))]


def _roster_opportunity_point(
    evidence: GatheredEvidence,
    school_name: str,
) -> Optional[TalkingPoint]:
    roster = evidence.roster_context
    same_family = _safe_int(roster.same_family_count)
    if same_family == 0:
        return None

    departures = _safe_int(roster.likely_departures_same_family)
    returning_high_usage = _safe_int(roster.returning_high_usage_same_family)

    if departures >= 3 and returning_high_usage <= 2:
        return TalkingPoint(
            kind="roster_opportunity",
            priority=10,
            fact=_strong_signal_fact(school_name, same_family, departures, returning_high_usage),
        )

    if departures >= 2:
        return TalkingPoint(
            kind="roster_opportunity",
            priority=12,
            fact=_moderate_signal_fact(school_name, same_family, departures),
        )

    if returning_high_usage >= 4 and departures <= 1:
        return TalkingPoint(
            kind="roster_opportunity",
            priority=14,
            fact=_crowded_signal_fact(school_name, returning_high_usage, departures),
        )

    return None


def _academic_angle_point(school: Dict[str, Any]) -> Optional[TalkingPoint]:
    label = (school.get("academic_fit") or "").strip()
    if label == "Strong Safety":
        return TalkingPoint(
            kind="academic_angle",
            priority=20,
            fact="academics are well within reach — the classroom won't be the battle",
        )
    if label == "Safety":
        return TalkingPoint(
            kind="academic_angle",
            priority=22,
            fact="academics are a comfortable match",
        )
    if label == "Reach":
        return TalkingPoint(
            kind="academic_angle",
            priority=21,
            fact=(
                "academically this is a stretch — the player should confirm "
                "grades and test scores are competitive"
            ),
        )
    if label == "Strong Reach":
        return TalkingPoint(
            kind="academic_angle",
            priority=18,
            fact=(
                "academically this is a real reach — admission isn't guaranteed "
                "and should be confirmed before investing time"
            ),
        )
    return None


def _location_clause(school: Dict[str, Any]) -> str:
    state = (
        school.get("location", {}).get("state")
        if isinstance(school.get("location"), dict)
        else school.get("state")
    )
    city = school.get("school_city")
    if city and state:
        return f" in {city}, {state}"
    if state:
        return f" in {state}"
    return ""


def _level_descriptor_point(school: Dict[str, Any]) -> Optional[TalkingPoint]:
    label = format_division_label(
        school.get("division_group") or "",
        school.get("baseball_division") or school.get("division"),
    )
    if not label:
        return None
    return TalkingPoint(
        kind="level_descriptor",
        priority=30,
        fact=f"competes at {label}{_location_clause(school)}",
    )


def compute_talking_points(
    school: Dict[str, Any],
    evidence: GatheredEvidence,
    player_stats: Dict[str, Any],
    is_pitcher: bool,
) -> List[TalkingPoint]:
    """Return up to 4 ranked talking points for the LLM narrative.

    Order (by priority field, ascending = more important):
      0-2  metric standouts (≥15% above level mean), magnitude-ordered
      10-14 roster opportunity from raw counts (skipped if no signal)
      18-22 academic angle (Reach/Strong Reach/Safety/Strong Safety)
      30   level + location descriptor (always last; connective tissue)
    """
    school_name = (
        school.get("display_school_name")
        or school.get("school_name")
        or ""
    )
    points: List[TalkingPoint] = []
    points.extend(_metric_standout_points(school, player_stats, is_pitcher))
    roster = _roster_opportunity_point(evidence, school_name)
    if roster:
        points.append(roster)
    acad = _academic_angle_point(school)
    if acad:
        points.append(acad)
    level = _level_descriptor_point(school)
    if level:
        points.append(level)
    points.sort(key=lambda p: p.priority)
    return points[:4]
