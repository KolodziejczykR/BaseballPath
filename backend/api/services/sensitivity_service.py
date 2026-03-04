"""
Sensitivity analysis service.
Re-runs the ML pipeline with perturbed inputs to rank stats by impact on D1/P4 probability.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from backend.ml.router.catcher_router import pipeline as catcher_pipeline
from backend.ml.router.infielder_router import pipeline as infielder_pipeline
from backend.ml.router.outfielder_router import pipeline as outfielder_pipeline
from backend.ml.router.pitcher_router import pipeline as pitcher_pipeline
from backend.utils.perturbable_stats import get_perturbable_stats
from backend.utils.player_types import (
    PlayerCatcher,
    PlayerInfielder,
    PlayerOutfielder,
    PlayerPitcher,
)

logger = logging.getLogger(__name__)

PIPELINE_MAP = {
    "infielder": infielder_pipeline,
    "outfielder": outfielder_pipeline,
    "catcher": catcher_pipeline,
    "pitcher": pitcher_pipeline,
}


def _as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _pick(identity: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in identity and identity.get(key) is not None:
            return identity.get(key)
    return default


def _build_player(position_track: str, stats: Dict[str, Any], identity: Dict[str, Any]):
    """Build a PlayerType object from stats + identity fields."""
    height = _as_int(_pick(identity, "height"), default=72)
    weight = _as_int(_pick(identity, "weight"), default=180)
    primary_position = str(
        _pick(
            identity,
            "primary_position",
            "primaryPosition",
            default="RHP" if position_track == "pitcher" else ("OF" if position_track == "outfielder" else "SS"),
        )
    ).upper()
    region = str(_pick(identity, "region", "player_region", "playerRegion", default="West"))
    throwing_hand = str(_pick(identity, "throwing_hand", "throwingHand", default="R")).upper()
    hitting_handedness = str(
        _pick(identity, "hitting_handedness", "hittingHandedness", "batting_hand", default="R")
    ).upper()

    if position_track == "infielder":
        return PlayerInfielder(
            height=height or 72,
            weight=weight or 180,
            primary_position=primary_position,
            hitting_handedness=hitting_handedness,
            throwing_hand=throwing_hand,
            region=region,
            exit_velo_max=float(stats.get("exit_velo_max")),
            inf_velo=float(stats.get("inf_velo")),
            sixty_time=float(stats.get("sixty_time")),
        )
    if position_track == "outfielder":
        return PlayerOutfielder(
            height=height or 72,
            weight=weight or 180,
            primary_position="OF" if primary_position not in {"OF"} else primary_position,
            hitting_handedness=hitting_handedness,
            throwing_hand=throwing_hand,
            region=region,
            exit_velo_max=float(stats.get("exit_velo_max")),
            of_velo=float(stats.get("of_velo")),
            sixty_time=float(stats.get("sixty_time")),
        )
    if position_track == "catcher":
        return PlayerCatcher(
            height=height or 72,
            weight=weight or 180,
            primary_position="C",
            hitting_handedness=hitting_handedness,
            throwing_hand=throwing_hand,
            region=region,
            exit_velo_max=float(stats.get("exit_velo_max")),
            c_velo=float(stats.get("c_velo")),
            pop_time=float(stats.get("pop_time")),
            sixty_time=float(stats.get("sixty_time")),
        )
    if position_track == "pitcher":
        return PlayerPitcher(
            height=height or 72,
            weight=weight or 180,
            primary_position=primary_position if primary_position in {"RHP", "LHP"} else "RHP",
            throwing_hand=throwing_hand if throwing_hand in {"R", "L"} else "R",
            region=region,
            fastball_velo_range=_as_float(stats.get("fastball_velo_range")),
            fastball_velo_max=_as_float(stats.get("fastball_velo_max")),
            fastball_spin=_as_float(stats.get("fastball_spin")),
            changeup_velo=_as_float(stats.get("changeup_velo")),
            changeup_spin=_as_float(stats.get("changeup_spin")),
            curveball_velo=_as_float(stats.get("curveball_velo")),
            curveball_spin=_as_float(stats.get("curveball_spin")),
            slider_velo=_as_float(stats.get("slider_velo")),
            slider_spin=_as_float(stats.get("slider_spin")),
        )
    raise ValueError(f"Unsupported position_track: {position_track}")


def _get_probability(result: Any, target_level: str) -> float:
    """Extract the relevant probability from MLPipelineResults."""
    if target_level == "Power 4 D1" and getattr(result, "p4_results", None):
        p4_results = getattr(result, "p4_results")
        p4_probability = getattr(p4_results, "p4_probability", None)
        if p4_probability is not None:
            return float(p4_probability)
    d1_results = getattr(result, "d1_results", None)
    if d1_results is None:
        raise ValueError("Missing d1_results from pipeline response")
    d1_probability = getattr(d1_results, "d1_probability", None)
    if d1_probability is None:
        raise ValueError("Missing d1_probability from pipeline response")
    return float(d1_probability)


def compute_sensitivity(
    position_track: str,
    current_stats: Dict[str, Any],
    identity_fields: Dict[str, Any],
    target_level: str = "D1",
) -> Dict[str, Any]:
    """
    Run sensitivity analysis for a player.

    Args:
        position_track: "infielder", "outfielder", "catcher", "pitcher"
        current_stats: Dict of stat_name -> current_value (only perturbable stats)
        identity_fields: Dict with height, weight, primary_position, region,
                         and handedness fields (not perturbed)
        target_level: "D1" or "Power 4 D1"

    Returns:
        Dict with base_probability and ranked perturbation results.
    """
    pipeline = PIPELINE_MAP.get(position_track)
    if pipeline is None:
        raise ValueError(f"No pipeline available for {position_track}")

    perturbable = get_perturbable_stats(position_track)

    # 1. Get base prediction
    base_player = _build_player(position_track, current_stats, identity_fields)
    base_result = pipeline.predict(base_player)
    base_prob = _get_probability(base_result, target_level)

    # 2. Perturb each stat and record deltas
    rankings = []
    for stat_name, config in perturbable.items():
        current_value = _as_float(current_stats.get(stat_name))
        if current_value is None:
            continue

        steps_results = []
        for step in config["steps"]:
            new_value = current_value + (float(step) * int(config["dir"]))
            if new_value <= 0:
                continue

            perturbed_stats = {**current_stats, stat_name: new_value}
            try:
                perturbed_player = _build_player(position_track, perturbed_stats, identity_fields)
                perturbed_result = pipeline.predict(perturbed_player)
                new_prob = _get_probability(perturbed_result, target_level)
            except Exception as exc:  # pragma: no cover - defensive path
                logger.warning("Sensitivity step failed for %s (%s): %s", stat_name, step, exc)
                continue

            steps_results.append(
                {
                    "delta": float(step),
                    "new_value": round(new_value, 3),
                    "new_probability": round(new_prob, 4),
                    "probability_change": round(new_prob - base_prob, 4),
                }
            )

        if not steps_results:
            continue

        max_impact = max(abs(entry["probability_change"]) for entry in steps_results)
        rankings.append(
            {
                "stat_name": stat_name,
                "display": config["display"],
                "unit": config["unit"],
                "current_value": round(current_value, 3),
                "direction": "increase" if config["dir"] == 1 else "decrease",
                "steps": steps_results,
                "max_impact": round(max_impact, 4),
            }
        )

    # 3. Sort by max impact (descending)
    rankings.sort(key=lambda entry: entry["max_impact"], reverse=True)

    return {
        "base_probability": round(base_prob, 4),
        "target_level": target_level,
        "position_track": position_track,
        "rankings": rankings,
    }
