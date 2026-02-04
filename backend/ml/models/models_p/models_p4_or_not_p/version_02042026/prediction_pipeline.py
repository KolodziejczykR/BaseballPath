#!/usr/bin/env python3
"""
Pitcher P4 Prediction Pipeline - Production Version
Simple LogReg + KNN model saved as a sklearn Pipeline.
"""

import json
import os
import sys
from typing import Dict, List

import pandas as pd
import joblib

# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.utils.prediction_types import P4PredictionResult


PITCH_FEATURES = [
    "FastballVelocity (max)",
    "FastballVelo Range",
    "FastballSpin Rate (avg)",
    "Changeup Velo Range",
    "Changeup Spin Rate (avg)",
    "Curveball Velo Range",
    "Curveball Spin Rate (avg)",
    "Slider Velo Range",
    "Slider Spin Rate (avg)",
]


def _infer_missing_flags(df: pd.DataFrame) -> pd.DataFrame:
    for col in PITCH_FEATURES:
        flag = f"{col}_missing"
        if flag not in df.columns:
            df[flag] = df[col].isna().astype(int)
    return df


def _infer_num_pitches_and_diffs(df: pd.DataFrame) -> pd.DataFrame:
    velo_cols = [
        "FastballVelo Range",
        "Changeup Velo Range",
        "Curveball Velo Range",
        "Slider Velo Range",
    ]
    if "num_pitches" not in df.columns:
        df["num_pitches"] = df[velo_cols].notna().sum(axis=1)

    def safe_diff(a, b):
        return a - b if pd.notna(a) and pd.notna(b) else None

    if "fb_ch_velo_diff" not in df.columns:
        df["fb_ch_velo_diff"] = df.apply(
            lambda r: safe_diff(r["FastballVelo Range"], r["Changeup Velo Range"]),
            axis=1,
        )
    if "fb_cb_velo_diff" not in df.columns:
        df["fb_cb_velo_diff"] = df.apply(
            lambda r: safe_diff(r["FastballVelo Range"], r["Curveball Velo Range"]),
            axis=1,
        )
    if "fb_sl_velo_diff" not in df.columns:
        df["fb_sl_velo_diff"] = df.apply(
            lambda r: safe_diff(r["FastballVelo Range"], r["Slider Velo Range"]),
            axis=1,
        )
    return df


def _prepare_features(player_data: Dict, feature_list: List[str]) -> pd.DataFrame:
    if "Region" not in player_data and "player_region" in player_data:
        player_data["Region"] = player_data.get("player_region")
    if "FastballVelo Range" not in player_data and "FastballVelo (avg)" in player_data:
        player_data["FastballVelo Range"] = player_data.get("FastballVelo (avg)")

    df = pd.DataFrame([player_data])
    df = _infer_missing_flags(df)
    df = _infer_num_pitches_and_diffs(df)

    for col in feature_list:
        if col not in df.columns:
            df[col] = None
    return df[feature_list]


def predict_pitcher_p4_probability(player_data: dict, models_dir: str, d1_probability: float) -> P4PredictionResult:
    """
    Predict P4 probability for pitchers (assumes D1).
    """
    model = joblib.load(os.path.join(models_dir, "logreg_knn_model.pkl"))
    with open(os.path.join(models_dir, "model_metadata.json"), "r") as f:
        meta = json.load(f)

    features = meta["features"]
    threshold = float(meta.get("threshold", 0.5))

    X = _prepare_features(player_data, features)
    p4_probability = float(model.predict_proba(X)[:, 1][0])
    p4_prediction = p4_probability >= threshold

    confidence = "High" if p4_probability >= 0.7 or p4_probability <= 0.3 else "Medium"

    return P4PredictionResult(
        p4_probability=p4_probability,
        p4_prediction=p4_prediction,
        confidence=confidence,
        is_elite=False,
        model_version=os.path.basename(models_dir),
        elite_indicators=None,
    )
