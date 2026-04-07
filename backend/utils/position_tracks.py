"""
Shared position normalization and track mapping helpers.

These constants keep catcher routing explicit and consistent across ML endpoints,
PCI logic, and persistence.
"""

from __future__ import annotations

from typing import Any

PITCHER_PRIMARY_POSITIONS = frozenset({"LHP", "RHP", "P", "PITCHER"})
OUTFIELDER_PRIMARY_POSITIONS = frozenset({"OF", "LF", "CF", "RF", "OUTFIELDER"})
CATCHER_PRIMARY_POSITIONS = frozenset({"C", "CATCHER"})

POSITION_TRACKS = frozenset({"pitcher", "infielder", "outfielder", "catcher"})


def normalize_primary_position(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().upper()


def is_pitcher_primary_position(value: Any) -> bool:
    return normalize_primary_position(value) in PITCHER_PRIMARY_POSITIONS


def primary_position_to_track(value: Any) -> str:
    pos = normalize_primary_position(value)
    if pos in PITCHER_PRIMARY_POSITIONS:
        return "pitcher"
    if pos in OUTFIELDER_PRIMARY_POSITIONS:
        return "outfielder"
    if pos in CATCHER_PRIMARY_POSITIONS:
        return "catcher"
    return "infielder"


def primary_position_to_hitter_bucket(value: Any) -> str:
    pos = normalize_primary_position(value)
    if pos in CATCHER_PRIMARY_POSITIONS:
        return "C"
    if pos in OUTFIELDER_PRIMARY_POSITIONS:
        return "OF"
    return "IF"
