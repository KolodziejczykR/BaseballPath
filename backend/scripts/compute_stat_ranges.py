"""
Compute and upsert percentile reference ranges for goals gap analysis.

Usage:
  cd backend
  python3 scripts/compute_stat_ranges.py --data-version v1
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

# Make sure "backend" is importable when script runs from backend/ or repo root.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
REPO_ROOT = os.path.dirname(BACKEND_DIR)
if REPO_ROOT not in sys.path:
    sys.path.append(REPO_ROOT)
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from api.clients.supabase import require_supabase_admin_client


@dataclass
class RangeRow:
    position_track: str
    level: str
    stat_name: str
    p10: Optional[float]
    p25: Optional[float]
    median: Optional[float]
    p75: Optional[float]
    p90: Optional[float]
    mean: Optional[float]
    std_dev: Optional[float]
    sample_count: int
    data_version: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "position_track": self.position_track,
            "level": self.level,
            "stat_name": self.stat_name,
            "p10": self.p10,
            "p25": self.p25,
            "median": self.median,
            "p75": self.p75,
            "p90": self.p90,
            "mean": self.mean,
            "std_dev": self.std_dev,
            "sample_count": self.sample_count,
            "data_version": self.data_version,
        }


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _summarize_numeric(
    *,
    series: pd.Series,
    position_track: str,
    level: str,
    stat_name: str,
    data_version: str,
) -> Optional[RangeRow]:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return None

    return RangeRow(
        position_track=position_track,
        level=level,
        stat_name=stat_name,
        p10=_safe_float(numeric.quantile(0.10)),
        p25=_safe_float(numeric.quantile(0.25)),
        median=_safe_float(numeric.quantile(0.50)),
        p75=_safe_float(numeric.quantile(0.75)),
        p90=_safe_float(numeric.quantile(0.90)),
        mean=_safe_float(numeric.mean()),
        std_dev=_safe_float(numeric.std(ddof=1)),
        sample_count=int(numeric.shape[0]),
        data_version=data_version,
    )


def _rows_from_binary_label(
    *,
    df: pd.DataFrame,
    position_track: str,
    label_column: str,
    stat_map: Dict[str, str],
    positive_level: str,
    negative_level: str,
    data_version: str,
) -> List[RangeRow]:
    rows: List[RangeRow] = []
    if label_column not in df.columns:
        return rows

    for label_value, level in ((1, positive_level), (0, negative_level)):
        subset = df[df[label_column] == label_value]
        if subset.empty:
            continue
        for source_column, stat_name in stat_map.items():
            if source_column not in subset.columns:
                continue
            summary = _summarize_numeric(
                series=subset[source_column],
                position_track=position_track,
                level=level,
                stat_name=stat_name,
                data_version=data_version,
            )
            if summary:
                rows.append(summary)
    return rows


def _read_csv(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def _compute_hitter_rows(data_version: str) -> List[RangeRow]:
    rows: List[RangeRow] = []

    d1_specs = [
        (
            "infielder",
            os.path.join(BACKEND_DIR, "data/hitters/inf_feat_eng.csv"),
            {"exit_velo_max": "exit_velo_max", "inf_velo": "inf_velo", "sixty_time": "sixty_time", "height": "height", "weight": "weight"},
        ),
        (
            "outfielder",
            os.path.join(BACKEND_DIR, "data/hitters/of_feat_eng_d1_or_not.csv"),
            {"exit_velo_max": "exit_velo_max", "of_velo": "of_velo", "sixty_time": "sixty_time", "height": "height", "weight": "weight"},
        ),
        (
            "catcher",
            os.path.join(BACKEND_DIR, "data/hitters/c_d1_or_not_data.csv"),
            {"exit_velo_max": "exit_velo_max", "c_velo": "c_velo", "pop_time": "pop_time", "sixty_time": "sixty_time", "height": "height", "weight": "weight"},
        ),
    ]

    for position_track, path, stat_map in d1_specs:
        df = _read_csv(path)
        rows.extend(
            _rows_from_binary_label(
                df=df,
                position_track=position_track,
                label_column="d1_or_not",
                stat_map=stat_map,
                positive_level="D1",
                negative_level="Non-D1",
                data_version=data_version,
            )
        )

    p4_specs = [
        (
            "infielder",
            os.path.join(BACKEND_DIR, "data/hitters/inf_p4_or_not_eng.csv"),
            {"exit_velo_max": "exit_velo_max", "inf_velo": "inf_velo", "sixty_time": "sixty_time", "height": "height", "weight": "weight"},
        ),
        (
            "outfielder",
            os.path.join(BACKEND_DIR, "data/hitters/of_p4_or_not_data.csv"),
            {"exit_velo_max": "exit_velo_max", "of_velo": "of_velo", "sixty_time": "sixty_time", "height": "height", "weight": "weight"},
        ),
        (
            "catcher",
            os.path.join(BACKEND_DIR, "data/hitters/c_p4_or_not_data.csv"),
            {"exit_velo_max": "exit_velo_max", "c_velo": "c_velo", "pop_time": "pop_time", "sixty_time": "sixty_time", "height": "height", "weight": "weight"},
        ),
    ]

    for position_track, path, stat_map in p4_specs:
        if not os.path.exists(path):
            continue
        df = _read_csv(path)
        rows.extend(
            _rows_from_binary_label(
                df=df,
                position_track=position_track,
                label_column="p4_or_not",
                stat_map=stat_map,
                positive_level="Power 4 D1",
                negative_level="Non-P4 D1",
                data_version=data_version,
            )
        )

    return rows


def _compute_pitcher_rows(data_version: str) -> List[RangeRow]:
    path = os.path.join(BACKEND_DIR, "data/pitchers/pitchers_data_clean.csv")
    df = _read_csv(path)

    stat_map = {
        "FastballVelocity (max)": "fastball_velo_max",
        "FastballVelo Range": "fastball_velo_range",
        "FastballSpin Rate (avg)": "fastball_spin",
        "Changeup Velo Range": "changeup_velo",
        "Curveball Velo Range": "curveball_velo",
        "Slider Velo Range": "slider_velo",
        "height": "height",
        "weight": "weight",
    }

    d1_groups = {"Power 4", "Low Major", "Mid Major"}
    power4_group = {"Power 4"}

    df = df.copy()
    df["d1_or_not"] = df["group"].apply(lambda value: 1 if value in d1_groups else 0)
    df["p4_or_not"] = df["group"].apply(lambda value: 1 if value in power4_group else 0)

    rows = []
    rows.extend(
        _rows_from_binary_label(
            df=df,
            position_track="pitcher",
            label_column="d1_or_not",
            stat_map=stat_map,
            positive_level="D1",
            negative_level="Non-D1",
            data_version=data_version,
        )
    )

    d1_only = df[df["d1_or_not"] == 1]
    rows.extend(
        _rows_from_binary_label(
            df=d1_only,
            position_track="pitcher",
            label_column="p4_or_not",
            stat_map=stat_map,
            positive_level="Power 4 D1",
            negative_level="Non-P4 D1",
            data_version=data_version,
        )
    )
    return rows


def compute_rows(data_version: str) -> List[Dict[str, Any]]:
    rows: List[RangeRow] = []
    rows.extend(_compute_hitter_rows(data_version))
    rows.extend(_compute_pitcher_rows(data_version))
    return [row.to_dict() for row in rows]


def chunked(iterable: List[Dict[str, Any]], size: int) -> Iterable[List[Dict[str, Any]]]:
    for start in range(0, len(iterable), size):
        yield iterable[start : start + size]


def upsert_rows(rows: List[Dict[str, Any]]) -> None:
    if not rows:
        print("No rows to upsert.")
        return
    supabase = require_supabase_admin_client()
    for batch in chunked(rows, 500):
        supabase.table("position_stat_ranges").upsert(
            batch,
            on_conflict="position_track,level,stat_name,data_version",
        ).execute()
    print(f"Upserted {len(rows)} position_stat_ranges rows.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute position stat ranges from training data.")
    parser.add_argument("--data-version", default="v1", help="Version label stored in position_stat_ranges.data_version")
    args = parser.parse_args()

    rows = compute_rows(args.data_version)
    upsert_rows(rows)


if __name__ == "__main__":
    main()
