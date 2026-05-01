"""Unit tests for backend/database/school_evidence_cache.py.

Stubs the Supabase client so tests are hermetic — no network, no real
DB. Verifies the freshness filter, the failed-status filter, and the
dataclass round-trip.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from backend.database import school_evidence_cache as cache_mod
from backend.llm.deep_school_insights.types import (
    MatchedPlayer,
    ParsedPlayer,
    ParsedStatLine,
)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


class _FakeSelect:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *_columns):
        return self

    def in_(self, _key, _values):
        return self

    def execute(self):
        return SimpleNamespace(data=self._rows)


class _FakeClient:
    def __init__(self, rows):
        self._rows = rows

    def table(self, _name):
        return _FakeSelect(self._rows)


def _patch_client(monkeypatch, rows):
    monkeypatch.setattr(
        cache_mod, "get_supabase_admin_client", lambda: _FakeClient(rows)
    )


def _row(
    school_name: str,
    *,
    age_days: float,
    source_status: str = "ok",
    matched_players: List[Dict[str, Any]] = None,
    roster_url: str = "https://example.edu/roster",
    stats_available: bool = True,
):
    fetched_at = datetime.now(timezone.utc) - timedelta(days=age_days)
    return {
        "school_name": school_name,
        "roster_url": roster_url,
        "matched_players": matched_players or [],
        "stats_available": stats_available,
        "source_status": source_status,
        "fetched_at": _iso(fetched_at),
    }


# ---------------------------------------------------------------------------
# load_cache_batch
# ---------------------------------------------------------------------------


def test_load_cache_batch_returns_fresh_rows(monkeypatch):
    _patch_client(monkeypatch, [_row("Stanford", age_days=2)])
    out = cache_mod.load_cache_batch(["Stanford"])
    assert "Stanford" in out
    assert out["Stanford"]["roster_url"] == "https://example.edu/roster"


def test_load_cache_batch_filters_stale_rows(monkeypatch):
    _patch_client(
        monkeypatch,
        [
            _row("Stanford", age_days=2),
            _row("OldSchool", age_days=cache_mod.TTL_DAYS + 1),
        ],
    )
    out = cache_mod.load_cache_batch(["Stanford", "OldSchool"])
    assert "Stanford" in out
    assert "OldSchool" not in out


def test_load_cache_batch_filters_failed_rows(monkeypatch):
    _patch_client(
        monkeypatch,
        [
            _row("Stanford", age_days=1, source_status="ok"),
            _row("Broken", age_days=1, source_status="failed"),
        ],
    )
    out = cache_mod.load_cache_batch(["Stanford", "Broken"])
    assert "Stanford" in out
    assert "Broken" not in out


def test_load_cache_batch_empty_input(monkeypatch):
    # Should never even hit the DB on empty input.
    monkeypatch.setattr(
        cache_mod, "get_supabase_admin_client",
        lambda: pytest.fail("client should not be created for empty input"),
    )
    assert cache_mod.load_cache_batch([]) == {}


def test_load_cache_batch_no_supabase_client_means_silent_miss(monkeypatch):
    monkeypatch.setattr(cache_mod, "get_supabase_admin_client", lambda: None)
    # Test envs without SUPABASE_URL/KEY shouldn't blow up the worker —
    # cache lookup just becomes a silent miss; live-fetch path runs.
    assert cache_mod.load_cache_batch(["Anything"]) == {}


def test_load_cache_batch_supabase_exception_means_silent_miss(monkeypatch):
    class _RaisingClient:
        def table(self, _name):
            raise RuntimeError("network down")

    monkeypatch.setattr(
        cache_mod, "get_supabase_admin_client", lambda: _RaisingClient()
    )
    # Connectivity blip during a worker run should degrade to live fetch,
    # not crash the evaluation.
    assert cache_mod.load_cache_batch(["Anything"]) == {}


# ---------------------------------------------------------------------------
# (de)serialize_matched_players
# ---------------------------------------------------------------------------


def _sample_matched() -> List[MatchedPlayer]:
    return [
        MatchedPlayer(
            player=ParsedPlayer(
                name="Alex Rodriguez",
                jersey_number="13",
                position_raw="SS",
                position_normalized="SS",
                position_family="IF",
                class_year_raw="Sophomore",
                normalized_class_year=2,
                is_redshirt=False,
                high_school="Westminster",
                previous_school=None,
                hometown="Miami, FL",
            ),
            batting_stats=ParsedStatLine(
                jersey_number="13", player_name="Alex Rodriguez",
                stat_type="batting", games_played=45, games_started=42,
            ),
            pitching_stats=None,
        ),
        MatchedPlayer(
            player=ParsedPlayer(name="No Stats Player", jersey_number=None),
            batting_stats=None,
            pitching_stats=None,
        ),
    ]


def test_serialize_then_deserialize_round_trip():
    original = _sample_matched()
    blob = cache_mod.serialize_matched_players(original)
    rehydrated = cache_mod.deserialize_matched_players(blob)
    assert rehydrated == original


def test_deserialize_handles_empty_or_none():
    assert cache_mod.deserialize_matched_players(None) == []
    assert cache_mod.deserialize_matched_players([]) == []


def test_deserialize_tolerates_unknown_extra_fields():
    """Schema drift: cache row written by an older/newer code version may
    include fields the dataclass doesn't recognize. Should not crash."""
    blob = [
        {
            "player": {
                "name": "Test Player",
                "jersey_number": "5",
                "future_field_we_dont_know_about": "ignored",
            },
            "batting_stats": None,
            "pitching_stats": None,
            "extra_top_level_field": "also_ignored",
        }
    ]
    rehydrated = cache_mod.deserialize_matched_players(blob)
    assert len(rehydrated) == 1
    assert rehydrated[0].player.name == "Test Player"


def test_deserialize_tolerates_missing_fields():
    """Schema drift other direction: dataclass got a new field after the
    cache row was written. Missing fields should fall back to defaults."""
    blob = [{"player": {"name": "Only Name"}}]
    rehydrated = cache_mod.deserialize_matched_players(blob)
    assert len(rehydrated) == 1
    assert rehydrated[0].player.name == "Only Name"
    assert rehydrated[0].player.jersey_number is None  # dataclass default
    assert rehydrated[0].batting_stats is None
    assert rehydrated[0].pitching_stats is None
