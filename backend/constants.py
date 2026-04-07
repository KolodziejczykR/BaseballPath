"""
Shared cross-domain constants for evaluation and matching.

This module is the stable import location for benchmark dictionaries used by
both evaluation and playing-time code paths.
"""

from backend.playing_time.constants import DIVISION_BENCHMARKS, PITCHER_DIVISION_BENCHMARKS

__all__ = ["DIVISION_BENCHMARKS", "PITCHER_DIVISION_BENCHMARKS"]
