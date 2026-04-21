"""Validate PCI tier placement for real P4 middle infielder commits."""

from backend.utils.school_group_constants import POWER_4_D1

from .conftest import assert_tier_accuracy, run_pci, sample_hitters


def test_p4_middle_infielders_tier_accuracy(hitter_df):
    players = sample_hitters(hitter_df, tier=POWER_4_D1, pos_group="MIF", n=100)
    results = [run_pci(p, is_pitcher=False) for p in players]
    assert_tier_accuracy(
        results,
        min_correct_pct=70.0,
        allow_adjacent=True,
        label="P4 Middle Infielders",
    )
