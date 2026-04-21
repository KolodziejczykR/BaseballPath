"""Validate PCI tier placement for real Non-P4 D1 pitcher commits."""

from backend.utils.school_group_constants import NON_P4_D1

from .conftest import assert_tier_accuracy, run_pci, sample_pitchers


def test_non_p4_d1_pitchers_tier_accuracy(pitcher_df):
    players = sample_pitchers(pitcher_df, tier=NON_P4_D1, n=100)
    results = [run_pci(p, is_pitcher=True) for p in players]
    assert_tier_accuracy(
        results,
        min_correct_pct=70.0,
        allow_adjacent=True,
        label="Non-P4 D1 Pitchers",
    )
