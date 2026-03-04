"""
Configuration for perturbable stats used in sensitivity analysis.
Maps position tracks to their modifiable stats with display info, direction, and step sizes.
"""

from __future__ import annotations

from typing import Any, Dict

PERTURBABLE_STATS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "infielder": {
        "exit_velo_max": {"display": "Exit Velocity", "unit": "mph", "dir": +1, "steps": [1, 2, 3, 5]},
        "inf_velo": {"display": "Infield Velocity", "unit": "mph", "dir": +1, "steps": [1, 2, 3, 5]},
        "sixty_time": {"display": "60-Yard Dash", "unit": "sec", "dir": -1, "steps": [0.05, 0.1, 0.2, 0.3]},
    },
    "outfielder": {
        "exit_velo_max": {"display": "Exit Velocity", "unit": "mph", "dir": +1, "steps": [1, 2, 3, 5]},
        "of_velo": {"display": "Outfield Velocity", "unit": "mph", "dir": +1, "steps": [1, 2, 3, 5]},
        "sixty_time": {"display": "60-Yard Dash", "unit": "sec", "dir": -1, "steps": [0.05, 0.1, 0.2, 0.3]},
    },
    "catcher": {
        "exit_velo_max": {"display": "Exit Velocity", "unit": "mph", "dir": +1, "steps": [1, 2, 3, 5]},
        "c_velo": {"display": "Catcher Velocity", "unit": "mph", "dir": +1, "steps": [1, 2, 3, 5]},
        "pop_time": {"display": "Pop Time", "unit": "sec", "dir": -1, "steps": [0.02, 0.05, 0.1, 0.15]},
        "sixty_time": {"display": "60-Yard Dash", "unit": "sec", "dir": -1, "steps": [0.05, 0.1, 0.2, 0.3]},
    },
    "pitcher": {
        "fastball_velo_max": {"display": "Fastball Max", "unit": "mph", "dir": +1, "steps": [1, 2, 3, 5]},
        "fastball_velo_range": {"display": "Fastball Avg", "unit": "mph", "dir": +1, "steps": [1, 2, 3, 5]},
        "fastball_spin": {"display": "Fastball Spin", "unit": "rpm", "dir": +1, "steps": [50, 100, 150, 200]},
        "changeup_velo": {"display": "Changeup Velo", "unit": "mph", "dir": +1, "steps": [1, 2, 3]},
        "curveball_velo": {"display": "Curveball Velo", "unit": "mph", "dir": +1, "steps": [1, 2, 3]},
        "slider_velo": {"display": "Slider Velo", "unit": "mph", "dir": +1, "steps": [1, 2, 3]},
    },
}


def get_perturbable_stats(position_track: str) -> Dict[str, Dict[str, Any]]:
    """Get perturbable stats config for a position track."""
    if position_track not in PERTURBABLE_STATS:
        raise ValueError(
            f"Unknown position_track: {position_track}. Must be one of: {list(PERTURBABLE_STATS.keys())}"
        )
    return PERTURBABLE_STATS[position_track]
