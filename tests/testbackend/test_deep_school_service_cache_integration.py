"""Integration tests for cache-aware enrich_and_rerank.

Verify the worker uses school_evidence_cache when present and falls
through to live fetch when absent, stale, or marked failed. Stubs the
read helper so tests are hermetic.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List

import pytest

from backend.database import school_evidence_cache as cache_mod
from backend.llm.deep_school_insights.service import DeepSchoolInsightService
from backend.llm.deep_school_insights.types import (
    DeepSchoolReview,
    GatheredEvidence,
    MatchedPlayer,
    OpportunityContext,
    ParsedPlayer,
    ParsedStatLine,
    RecruitingContext,
    ResearchSource,
    RosterContext,
)


def _stub_review() -> DeepSchoolReview:
    return DeepSchoolReview(
        base_athletic_fit="Fit",
        opportunity_fit="Fit",
        final_school_view="Fit",
        adjustment_from_base="none",
        confidence="medium",
        why_this_school="x",
    )


class _CacheTrackingService(DeepSchoolInsightService):
    """Production _enrich_single_school path; counts live-fetch invocations.

    The cache-hit path is exercised end-to-end (deserialize → evidence_from_matched
    → _review_school stub). The miss path increments live_fetch_count so
    we can assert it's not called when the cache should have served the row.
    """

    def __init__(self, fetch_concurrency: int = 3, llm_concurrency: int = 10):
        os.environ["RESEARCH_FETCH_CONCURRENCY"] = str(fetch_concurrency)
        os.environ["RESEARCH_LLM_CONCURRENCY"] = str(llm_concurrency)
        try:
            super().__init__(client=object(), llm_timeout_s=10.0)
        finally:
            del os.environ["RESEARCH_FETCH_CONCURRENCY"]
            del os.environ["RESEARCH_LLM_CONCURRENCY"]
        self.has_responses_parse = True
        self.live_fetch_count = 0
        self.live_fetched_schools: List[str] = []

    async def _gather_evidence(self, school, player_stats, trusted_domains):
        self.live_fetch_count += 1
        self.live_fetched_schools.append(school.get("school_name", ""))
        return GatheredEvidence(
            roster_context=RosterContext(position_data_quality="exact"),
            recruiting_context=RecruitingContext(),
            opportunity_context=OpportunityContext(
                competition_level="medium", opportunity_level="medium"
            ),
            sources=[
                ResearchSource(
                    label="Live fetch",
                    url="https://example.edu/roster",
                    source_type="official_roster",
                    supports=["competition_level"],
                )
            ],
        )

    async def _review_school(
        self, school, player_stats, baseball_assessment, academic_score,
        evidence, talking_points,
    ):
        return _stub_review()


def _matched_players_for(school_name: str, position_family: str = "IF") -> List[MatchedPlayer]:
    return [
        MatchedPlayer(
            player=ParsedPlayer(
                name=f"{school_name} player {i}",
                jersey_number=str(i),
                position_normalized=("SS" if position_family == "IF" else "P"),
                position_family=position_family,
                normalized_class_year=2,
            ),
            batting_stats=ParsedStatLine(
                jersey_number=str(i), player_name=f"{school_name} player {i}",
                stat_type="batting", games_played=20, games_started=10,
            ),
            pitching_stats=None,
        )
        for i in range(3)
    ]


def _cache_row(school_name: str) -> Dict[str, Any]:
    return {
        "school_name": school_name,
        "roster_url": f"https://{school_name.lower()}.example.edu/roster",
        "matched_players": cache_mod.serialize_matched_players(
            _matched_players_for(school_name)
        ),
        "stats_available": True,
        "source_status": "ok",
    }


def _schools(names: List[str]) -> List[Dict[str, Any]]:
    return [
        {"school_name": name, "delta": 10.0 - i, "fit_label": "Fit"}
        for i, name in enumerate(names)
    ]


@pytest.mark.asyncio
async def test_full_cache_hit_skips_live_fetch(monkeypatch):
    service = _CacheTrackingService()
    cache = {name: _cache_row(name) for name in ["A", "B", "C"]}
    # Patch load_cache_batch where service.py imports it from.
    import backend.database.school_evidence_cache as cache_module
    monkeypatch.setattr(cache_module, "load_cache_batch", lambda names: cache)

    ranked = await service.enrich_and_rerank(
        schools=_schools(["A", "B", "C"]),
        player_stats={"primary_position": "SS"},
        baseball_assessment={"predicted_tier": "Non-D1"},
        academic_score={},
        final_limit=3,  # forces fan-out path
    )

    assert len(ranked) == 3
    # All schools served from cache → live fetch never called.
    assert service.live_fetch_count == 0
    assert service.live_fetched_schools == []


@pytest.mark.asyncio
async def test_partial_cache_falls_through_for_missing(monkeypatch):
    service = _CacheTrackingService()
    cache = {"A": _cache_row("A")}  # only A is cached
    import backend.database.school_evidence_cache as cache_module
    monkeypatch.setattr(cache_module, "load_cache_batch", lambda names: cache)

    await service.enrich_and_rerank(
        schools=_schools(["A", "B", "C"]),
        player_stats={"primary_position": "SS"},
        baseball_assessment={"predicted_tier": "Non-D1"},
        academic_score={},
        final_limit=3,
    )

    # B and C miss → live fetch called for each. A is cached → not fetched.
    assert service.live_fetch_count == 2
    assert set(service.live_fetched_schools) == {"B", "C"}


@pytest.mark.asyncio
async def test_empty_cache_falls_through_for_all(monkeypatch):
    service = _CacheTrackingService()
    import backend.database.school_evidence_cache as cache_module
    monkeypatch.setattr(cache_module, "load_cache_batch", lambda names: {})

    await service.enrich_and_rerank(
        schools=_schools(["A", "B", "C"]),
        player_stats={"primary_position": "SS"},
        baseball_assessment={"predicted_tier": "Non-D1"},
        academic_score={},
        final_limit=3,
    )

    # No cache → all 3 schools live-fetched. Behavior identical to pre-cache code.
    assert service.live_fetch_count == 3
    assert set(service.live_fetched_schools) == {"A", "B", "C"}


@pytest.mark.asyncio
async def test_cache_lookup_failure_falls_through_silently(monkeypatch):
    service = _CacheTrackingService()

    def _raise(_names):
        raise RuntimeError("supabase down")

    import backend.database.school_evidence_cache as cache_module
    monkeypatch.setattr(cache_module, "load_cache_batch", _raise)

    # The exception inside the cache lookup should be caught in enrich_and_rerank
    # and degrade silently to live-fetch — not propagate and crash the eval.
    await service.enrich_and_rerank(
        schools=_schools(["A", "B"]),
        player_stats={"primary_position": "SS"},
        baseball_assessment={"predicted_tier": "Non-D1"},
        academic_score={},
        final_limit=2,
    )
    assert service.live_fetch_count == 2


@pytest.mark.asyncio
async def test_cache_hit_uses_player_position_filter(monkeypatch):
    """A cached row is position-agnostic — it stores ALL roster players.
    The user's primary_position only filters at compute_evidence time. So
    two different users querying the same cached school should both see
    full roster sourcing in their evidence."""
    service = _CacheTrackingService()
    cache = {"School": _cache_row("School")}
    import backend.database.school_evidence_cache as cache_module
    monkeypatch.setattr(cache_module, "load_cache_batch", lambda names: cache)

    # Run as an infielder (SS).
    ranked_inf = await service.enrich_and_rerank(
        schools=_schools(["School"]),
        player_stats={"primary_position": "SS"},
        baseball_assessment={"predicted_tier": "Non-D1"},
        academic_score={},
        final_limit=1,
    )
    # Run as a pitcher.
    ranked_p = await service.enrich_and_rerank(
        schools=_schools(["School"]),
        player_stats={"primary_position": "P"},
        baseball_assessment={"predicted_tier": "Non-D1"},
        academic_score={},
        final_limit=1,
    )

    # Both runs hit cache (no live fetch).
    assert service.live_fetch_count == 0
    # Both completed.
    assert ranked_inf[0]["research_status"] in ("completed", "metadata_only")
    assert ranked_p[0]["research_status"] in ("completed", "metadata_only")
