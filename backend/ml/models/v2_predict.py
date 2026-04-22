"""
V2 Prediction Module -- Calibrated XGBoost models (isotonic).

All v2 models share the same structure:
  - calibrated_xgb_model.pkl  (XGBoost + CalibratedClassifierCV isotonic)
  - model_config.json         (features, threshold, metrics)
  - feature_metadata.json     (features, required_columns, notes)

No feature engineering, no scaling -- raw features only.
XGBoost handles NaN natively for missing stats.
"""

import json
import os

import joblib
import numpy as np
import pandas as pd

from backend.utils.prediction_types import D1PredictionResult, P4PredictionResult

# Maps API / PlayerType field names -> v2 model feature names.
# Only needed where the training CSV used different column names.
_FEATURE_ALIASES = {
    "changeup_velo": "changeup_velo_range",
    "curveball_velo": "curveball_velo_range",
    "slider_velo": "slider_velo_range",
}


def _load_model_and_config(model_dir: str):
    model = joblib.load(os.path.join(model_dir, "calibrated_xgb_model.pkl"))
    with open(os.path.join(model_dir, "model_config.json"), "r") as f:
        config = json.load(f)
    return model, config


def _build_feature_df(player_data: dict, features: list) -> pd.DataFrame:
    """Single-row DataFrame with exactly the features the model expects.

    Applies _FEATURE_ALIASES so that e.g. player_data["changeup_velo"]
    fills the model's "changeup_velo_range" column.  Anything still
    missing is left as NaN -- XGBoost handles it natively.
    """
    row = {}
    for feat in features:
        if feat in player_data and player_data[feat] is not None:
            row[feat] = player_data[feat]
        else:
            # Try alias lookup (alias key in player_data -> target feat name)
            for alias, target in _FEATURE_ALIASES.items():
                if target == feat and alias in player_data and player_data[alias] is not None:
                    row[feat] = player_data[alias]
                    break
            else:
                row[feat] = np.nan
    df = pd.DataFrame([row], columns=features)
    # Force all columns to float so XGBoost can handle NaN natively.
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _confidence_label(probability: float, threshold: float) -> str:
    distance = abs(probability - threshold)
    if distance > 0.25:
        return "High"
    if distance > 0.10:
        return "Medium"
    return "Low"


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


def predict_d1(player_data: dict, model_dir: str) -> D1PredictionResult:
    """Run a v2 calibrated-XGBoost D1 prediction."""
    model, config = _load_model_and_config(model_dir)
    features = config["features"]
    threshold = config["threshold"]

    X = _build_feature_df(player_data, features)
    d1_prob = float(model.predict_proba(X)[0, 1])

    return D1PredictionResult(
        d1_probability=d1_prob,
        d1_prediction=d1_prob >= threshold,
        confidence=_confidence_label(d1_prob, threshold),
        model_version=config.get("model_version", os.path.basename(model_dir)),
    )


def predict_p4(
    player_data: dict,
    model_dir: str,
    d1_probability: float,
) -> P4PredictionResult:
    """Run a v2 calibrated-XGBoost P4 prediction.

    ``d1_probability`` from the D1 stage is injected as the ``d1_prob``
    meta-feature expected by every P4 model.
    """
    model, config = _load_model_and_config(model_dir)
    features = config["features"]
    threshold = config["threshold"]

    augmented = dict(player_data)
    augmented["d1_prob"] = d1_probability

    X = _build_feature_df(augmented, features)
    p4_prob = float(model.predict_proba(X)[0, 1])

    return P4PredictionResult(
        p4_probability=p4_prob,
        p4_prediction=p4_prob >= threshold,
        confidence=_confidence_label(p4_prob, threshold),
        is_elite=p4_prob >= 0.65,
        model_version=config.get("model_version", config.get("version", os.path.basename(model_dir))),
        elite_indicators=None,
    )
