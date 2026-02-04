"""
Clean pitcher dataset for modeling.

Input:
  backend/data/pitchers/pitch_by_position_with_features.csv

Output:
  backend/data/pitchers/pitchers_data_clean.csv

Operations performed:
  - Drop non-modeling columns: age, class, hitting_handedness, conference,
    conf_short, college_location, division, commitment.
  - Clean throwing_hand: strip whitespace, uppercase, keep only L/R.
  - Clean primary_position: strip whitespace, uppercase, keep only LHP/RHP.
  - Clean positions: reduce to LHP/RHP if present; drop others.
  - Clean Region: keep only Northeast, South, Midwest, West (drop Canada/empty).
  - Remove extreme height/weight outliers using fixed bounds:
      height in [63, 84] inches; weight in [80, 290] pounds.
"""

from pathlib import Path
import numpy as np
import pandas as pd


def clean_pitcher_data(
    in_path: Path = Path("backend/data/pitchers/pitch_by_position_with_features.csv"),
    out_path: Path = Path("/Users/ryankolodziejczyk/Documents/AI Baseball Recruitment/code/backend/data/pitchers/pitchers_data_clean.csv"),
) -> None:
    df = pd.read_csv('/Users/ryankolodziejczyk/Documents/AI Baseball Recruitment/code/backend/data/pitchers/pitch_by_position_with_features.csv')

    # Drop columns not used for pitcher modeling or target creation
    cols_to_drop = [
        "name",
        "link",
        "state",
        "school",
        "positions",
        "Division of Region",
        "confidence",
        "age",
        "class",
        "hitting_handedness",
        "conference",
        "conf_short",
        "college_location",
        "division",
        "commitment",
    ]
    df = df.drop(columns=[c for c in cols_to_drop if c in df.columns])

    # Clean throwing hand
    if "throwing_hand" in df.columns:
        df["throwing_hand"] = df["throwing_hand"].astype(str).str.strip().str.upper()
        df = df[df["throwing_hand"].isin(["L", "R"])]

    # Clean primary position
    if "primary_position" in df.columns:
        df["primary_position"] = df["primary_position"].astype(str).str.strip().str.upper()
        df = df[df["primary_position"].isin(["LHP", "RHP"])]

    # Clean positions (reduce to LHP/RHP)
    if "positions" in df.columns:
        pos = df["positions"].astype(str).str.upper()

        def norm_pos(s: str):
            if "LHP" in s:
                return "LHP"
            if "RHP" in s:
                return "RHP"
            return np.nan

        df["positions"] = pos.map(norm_pos)
        df = df[df["positions"].isin(["LHP", "RHP"])]

    # Clean Region
    if "Region" in df.columns:
        df["Region"] = df["Region"].astype(str).str.strip().str.title()
        df = df[df["Region"].isin(["Northeast", "South", "Midwest", "West"])]

    # Remove extreme height/weight outliers (fixed bounds)
    bounds = {
        "height": (63, 82), # 5'3" to 7'2"
        "weight": (80, 290),
    }
    for col, (lo, hi) in bounds.items():
        if col in df.columns:
            df = df[df[col].isna() | ((df[col] >= lo) & (df[col] <= hi))]

    df.to_csv(out_path, index=False)


if __name__ == "__main__":
    clean_pitcher_data()
