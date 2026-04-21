"""
Shared fixtures and helpers for PCI validation tests.

Loads real player data from the commitment CSVs, samples players stratified
by within-tier z-score (elite / normal / borderline), and runs them through
the PCI pipeline to verify tier placement accuracy.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import pytest

from backend.evaluation.competitiveness import effective_tier
from backend.evaluation.school_matching import (
    compute_player_pci,
    compute_within_tier_percentile,
)
from backend.utils.school_group_constants import NON_D1, NON_P4_D1, POWER_4_D1

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).resolve().parents[2] / "backend" / "data"
HITTERS_CSV = _DATA_DIR / "hitters" / "all_hitter_data.csv"
PITCHERS_CSV = _DATA_DIR / "pitchers" / "pitchers_data_clean.csv"

# ---------------------------------------------------------------------------
# Position groupings (match benchmark structure)
# ---------------------------------------------------------------------------

MIF_POSITIONS = ["SS", "2B", "MIF"]
CIF_POSITIONS = ["3B", "1B"]
OF_POSITIONS = ["OF", "CF", "RF", "LF"]
C_POSITIONS = ["C"]

POSITION_GROUP_MAP = {
    "OF": OF_POSITIONS,
    "MIF": MIF_POSITIONS,
    "CIF": CIF_POSITIONS,
    "C": C_POSITIONS,
}

# Representative primary_position for each group (used in PCI input)
POSITION_GROUP_REPRESENTATIVE = {
    "OF": "OF",
    "MIF": "SS",
    "CIF": "3B",
    "C": "C",
}

# ---------------------------------------------------------------------------
# Tier mapping
# ---------------------------------------------------------------------------

HITTER_TIER_MAP = {
    "Power 4 D1": POWER_4_D1,
    "Non P4 D1": NON_P4_D1,
}

PITCHER_GROUP_TO_TIER = {
    "Power 4": POWER_4_D1,
    "Mid Major": NON_P4_D1,
    "Low Major": NON_P4_D1,
    "D2": NON_D1,
    "D3": NON_D1,
}

# ---------------------------------------------------------------------------
# Data loading (cached per session)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def hitter_df() -> pd.DataFrame:
    df = pd.read_csv(HITTERS_CSV)
    # Map tiers — Non D1 needs committment_group filter for D2/D3
    tier_col = []
    for _, row in df.iterrows():
        tsg = row["three_section_commit_group"]
        if tsg in HITTER_TIER_MAP:
            tier_col.append(HITTER_TIER_MAP[tsg])
        elif tsg == "Non D1" and row.get("committment_group") in ("D2", "D3"):
            tier_col.append(NON_D1)
        else:
            tier_col.append(None)
    df["tier"] = tier_col
    return df[df["tier"].notna()].copy()


@pytest.fixture(scope="session")
def pitcher_df() -> pd.DataFrame:
    df = pd.read_csv(PITCHERS_CSV)
    df["tier"] = df["group"].map(PITCHER_GROUP_TO_TIER)
    return df[df["tier"].notna()].copy()


# ---------------------------------------------------------------------------
# Stat sufficiency filters
# ---------------------------------------------------------------------------


def _hitter_has_stats(row: pd.Series, pos_group: str) -> bool:
    if pd.isna(row.get("exit_velo_max")) or pd.isna(row.get("sixty_time")):
        return False
    if pos_group == "OF":
        return pd.notna(row.get("of_velo"))
    if pos_group in ("MIF", "CIF"):
        return pd.notna(row.get("inf_velo"))
    if pos_group == "C":
        return pd.notna(row.get("c_velo"))
    return False


def _pitcher_has_stats(row: pd.Series) -> bool:
    has_fb = pd.notna(row.get("FastballVelocity (max)")) or pd.notna(
        row.get("FastballVelo Range")
    )
    secondaries = sum(
        1
        for col in [
            "Changeup Velo Range",
            "Curveball Velo Range",
            "Slider Velo Range",
        ]
        if pd.notna(row.get(col))
    )
    return has_fb and secondaries >= 1


# ---------------------------------------------------------------------------
# Build player_stats dict from a CSV row
# ---------------------------------------------------------------------------


def hitter_row_to_stats(row: pd.Series, pos_group: str) -> Dict[str, Any]:
    """Convert a hitter CSV row to the dict format compute_player_pci expects."""
    stats: Dict[str, Any] = {
        "primary_position": POSITION_GROUP_REPRESENTATIVE[pos_group],
        "height": int(row["height"]) if pd.notna(row.get("height")) else 72,
        "weight": int(row["weight"]) if pd.notna(row.get("weight")) else 180,
    }
    for col in ("exit_velo_max", "sixty_time", "inf_velo", "of_velo", "c_velo", "pop_time"):
        val = row.get(col)
        if pd.notna(val):
            stats[col] = float(val)
    return stats


def pitcher_row_to_stats(row: pd.Series) -> Dict[str, Any]:
    """Convert a pitcher CSV row to the dict format compute_player_pci expects."""
    stats: Dict[str, Any] = {
        "primary_position": str(row.get("primary_position", "RHP")),
        "height": int(row["height"]) if pd.notna(row.get("height")) else 74,
        "weight": int(row["weight"]) if pd.notna(row.get("weight")) else 185,
    }
    col_map = {
        "FastballVelocity (max)": "fastball_velo_max",
        "FastballVelo Range": "fastball_velo_range",
        "FastballSpin Rate (avg)": "fastball_spin",
        "Changeup Velo Range": "changeup_velo",
        "Changeup Spin Rate (avg)": "changeup_spin",
        "Curveball Velo Range": "curveball_velo",
        "Curveball Spin Rate (avg)": "curveball_spin",
        "Slider Velo Range": "slider_velo",
        "Slider Spin Rate (avg)": "slider_spin",
    }
    for csv_col, stat_key in col_map.items():
        val = row.get(csv_col)
        if pd.notna(val):
            stats[stat_key] = float(val)
    return stats


# ---------------------------------------------------------------------------
# Sampling: stratified by within-tier z-score
# ---------------------------------------------------------------------------

# Simulated ML probabilities by actual commitment tier.
# These represent what a reasonable ML model would output for a player
# who actually committed at this level.
_SIMULATED_PROBS = {
    POWER_4_D1: {"d1_probability": 0.85, "p4_probability": 0.70},
    NON_P4_D1: {"d1_probability": 0.72, "p4_probability": 0.20},
    NON_D1: {"d1_probability": 0.18, "p4_probability": 0.02},
}


def sample_hitters(
    df: pd.DataFrame,
    tier: str,
    pos_group: str,
    n: int = 100,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """
    Sample n real hitters from the given tier + position group.

    Returns a list of dicts with keys: player_stats, actual_tier,
    d1_probability, p4_probability, player_name.

    Players are stratified: ~30 elite (top 20%), ~40 normal (20-80%),
    ~30 borderline (bottom 20%) based on within-tier percentile.
    """
    positions = POSITION_GROUP_MAP[pos_group]
    pool = df[
        (df["tier"] == tier)
        & (df["primary_position"].isin(positions))
    ].copy()

    # Filter to players with sufficient stats
    mask = pool.apply(lambda r: _hitter_has_stats(r, pos_group), axis=1)
    pool = pool[mask].copy()

    if len(pool) == 0:
        return []

    # Compute within-tier percentile for stratification
    pcts = []
    for _, row in pool.iterrows():
        stats = hitter_row_to_stats(row, pos_group)
        pct = compute_within_tier_percentile(
            player_stats=stats,
            predicted_tier=tier,
            is_pitcher=False,
            player_position=stats["primary_position"],
        )
        pcts.append(pct)
    pool["_pct"] = pcts

    # Stratify
    elite = pool[pool["_pct"] >= pool["_pct"].quantile(0.80)]
    normal = pool[(pool["_pct"] >= pool["_pct"].quantile(0.20)) & (pool["_pct"] < pool["_pct"].quantile(0.80))]
    borderline = pool[pool["_pct"] < pool["_pct"].quantile(0.20)]

    rng = pd.np if hasattr(pd, "np") else __import__("numpy")
    rs = rng.random.RandomState(seed)

    n_elite = min(30, len(elite), n)
    n_borderline = min(30, len(borderline), max(0, n - n_elite))
    n_normal = min(len(normal), max(0, n - n_elite - n_borderline))

    sampled = pd.concat([
        elite.sample(n=n_elite, random_state=rs) if n_elite > 0 else elite.iloc[:0],
        normal.sample(n=n_normal, random_state=rs) if n_normal > 0 else normal.iloc[:0],
        borderline.sample(n=n_borderline, random_state=rs) if n_borderline > 0 else borderline.iloc[:0],
    ])

    probs = _SIMULATED_PROBS[tier]
    results = []
    for _, row in sampled.iterrows():
        stats = hitter_row_to_stats(row, pos_group)
        name = str(row.get("come", "Unknown"))
        results.append({
            "player_stats": stats,
            "actual_tier": tier,
            "d1_probability": probs["d1_probability"],
            "p4_probability": probs["p4_probability"],
            "player_name": name,
            "within_tier_pct": row["_pct"],
        })
    return results


def sample_pitchers(
    df: pd.DataFrame,
    tier: str,
    n: int = 100,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """Sample n real pitchers from the given tier, stratified by percentile."""
    pool = df[df["tier"] == tier].copy()
    mask = pool.apply(_pitcher_has_stats, axis=1)
    pool = pool[mask].copy()

    if len(pool) == 0:
        return []

    pcts = []
    for _, row in pool.iterrows():
        stats = pitcher_row_to_stats(row)
        pct = compute_within_tier_percentile(
            player_stats=stats,
            predicted_tier=tier,
            is_pitcher=True,
        )
        pcts.append(pct)
    pool["_pct"] = pcts

    elite = pool[pool["_pct"] >= pool["_pct"].quantile(0.80)]
    normal = pool[(pool["_pct"] >= pool["_pct"].quantile(0.20)) & (pool["_pct"] < pool["_pct"].quantile(0.80))]
    borderline = pool[pool["_pct"] < pool["_pct"].quantile(0.20)]

    rng = __import__("numpy")
    rs = rng.random.RandomState(seed)

    n_elite = min(30, len(elite), n)
    n_borderline = min(30, len(borderline), max(0, n - n_elite))
    n_normal = min(len(normal), max(0, n - n_elite - n_borderline))

    sampled = pd.concat([
        elite.sample(n=n_elite, random_state=rs) if n_elite > 0 else elite.iloc[:0],
        normal.sample(n=n_normal, random_state=rs) if n_normal > 0 else normal.iloc[:0],
        borderline.sample(n=n_borderline, random_state=rs) if n_borderline > 0 else borderline.iloc[:0],
    ])

    probs = _SIMULATED_PROBS[tier]
    results = []
    for _, row in sampled.iterrows():
        stats = pitcher_row_to_stats(row)
        results.append({
            "player_stats": stats,
            "actual_tier": tier,
            "d1_probability": probs["d1_probability"],
            "p4_probability": probs["p4_probability"],
            "player_name": f"Pitcher_{row.name}",
            "within_tier_pct": row["_pct"],
        })
    return results


# ---------------------------------------------------------------------------
# PCI runner
# ---------------------------------------------------------------------------


def run_pci(player: Dict[str, Any], is_pitcher: bool) -> Dict[str, Any]:
    """Run a sampled player through the full PCI pipeline and return results."""
    actual_tier = player["actual_tier"]
    d1_prob = player["d1_probability"]
    p4_prob = player["p4_probability"]

    # effective_tier runs first (as it does in the real pipeline)
    predicted_tier = effective_tier(
        actual_tier,
        d1_probability=d1_prob,
        p4_probability=p4_prob,
    )

    result = compute_player_pci(
        player_stats=player["player_stats"],
        predicted_tier=predicted_tier,
        d1_probability=d1_prob,
        p4_probability=p4_prob,
        is_pitcher=is_pitcher,
    )

    return {
        "player_name": player["player_name"],
        "actual_tier": actual_tier,
        "ml_predicted_tier": actual_tier,  # simulating correct ML prediction
        "effective_tier": predicted_tier,
        "final_tier": result["predicted_tier"],
        "within_tier_pct": result["within_tier_percentile"],
        "player_pci": result["player_pci"],
        "was_demoted": result["predicted_tier"] != predicted_tier,
        "tiers_dropped": _tier_distance(predicted_tier, result["predicted_tier"]),
        "original_within_tier_pct": player["within_tier_pct"],
    }


def _tier_distance(from_tier: str, to_tier: str) -> int:
    order = [POWER_4_D1, NON_P4_D1, NON_D1]
    try:
        return order.index(to_tier) - order.index(from_tier)
    except ValueError:
        return 0


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------


def assert_tier_accuracy(
    results: List[Dict[str, Any]],
    *,
    min_correct_pct: float = 70.0,
    allow_adjacent: bool = True,
    label: str = "",
):
    """
    Assert that at least min_correct_pct of players land in the correct tier
    (or an adjacent tier if allow_adjacent=True).

    Prints a detailed breakdown regardless of pass/fail.
    """
    total = len(results)
    if total == 0:
        pytest.skip("No players sampled")

    exact_match = sum(1 for r in results if r["final_tier"] == r["actual_tier"])
    demoted = [r for r in results if r["tiers_dropped"] > 0]
    promoted = [r for r in results if r["tiers_dropped"] < 0]

    adjacent_match = sum(
        1 for r in results if abs(r["tiers_dropped"]) <= 1
    )

    check_count = adjacent_match if allow_adjacent else exact_match
    accuracy = (check_count / total) * 100.0

    # Always print breakdown for visibility
    print(f"\n{'=' * 60}")
    print(f"  {label or 'Tier Placement Accuracy'}")
    print(f"{'=' * 60}")
    print(f"  Total players:    {total}")
    print(f"  Exact tier match: {exact_match} ({exact_match/total*100:.1f}%)")
    print(f"  Adjacent match:   {adjacent_match} ({adjacent_match/total*100:.1f}%)")
    print(f"  Demoted:          {len(demoted)} ({len(demoted)/total*100:.1f}%)")
    if demoted:
        drop_counts = {}
        for r in demoted:
            key = f"{r['actual_tier']} -> {r['final_tier']}"
            drop_counts[key] = drop_counts.get(key, 0) + 1
        for path, count in sorted(drop_counts.items()):
            print(f"    {path}: {count}")

    # PCI distribution
    pcis = [r["player_pci"] for r in results]
    print(f"\n  PCI range: {min(pcis):.1f} - {max(pcis):.1f}")
    print(f"  PCI mean:  {sum(pcis)/len(pcis):.1f}")
    print(f"  PCI median: {sorted(pcis)[len(pcis)//2]:.1f}")

    mode = "adjacent" if allow_adjacent else "exact"
    assert accuracy >= min_correct_pct, (
        f"{label}: {mode} tier accuracy {accuracy:.1f}% < {min_correct_pct}% threshold. "
        f"{len(demoted)} demoted, {len(promoted)} promoted out of {total}."
    )
