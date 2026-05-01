"""Concurrency-cap regression tests for the fan-out path in
DeepSchoolInsightService.enrich_and_rerank.

The fan-out path uses two asyncio.Semaphores so HTML fetches stay
RAM-bounded (~3 in flight) while LLM calls fan out wider (~10) for
speed. If anyone removes the semaphores or wires them wrong, RAM ceiling
breaks under concurrent users. These tests stub the I/O steps with
counted async functions and assert the caps hold.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List

import pytest

from backend.llm.deep_school_insights.service import DeepSchoolInsightService
from backend.llm.deep_school_insights.types import (
    DeepSchoolReview,
    GatheredEvidence,
    OpportunityContext,
    RecruitingContext,
    ResearchSource,
    RosterContext,
)


def _evidence() -> GatheredEvidence:
    return GatheredEvidence(
        roster_context=RosterContext(position_data_quality="exact"),
        recruiting_context=RecruitingContext(),
        opportunity_context=OpportunityContext(
            competition_level="medium", opportunity_level="medium"
        ),
        sources=[
            ResearchSource(
                label="Test roster",
                url="https://example.edu/roster",
                source_type="official_roster",
                supports=["competition_level"],
            )
        ],
    )


def _review() -> DeepSchoolReview:
    return DeepSchoolReview(
        base_athletic_fit="Fit",
        opportunity_fit="Fit",
        final_school_view="Fit",
        adjustment_from_base="none",
        confidence="medium",
        why_this_school="x",
    )


class _CountingService(DeepSchoolInsightService):
    """Production _enrich_single_school path with stubbed I/O.

    _gather_evidence and _review_school each track concurrent occupancy
    so the test can assert the semaphore caps hold across the run.
    """

    def __init__(self, fetch_concurrency: int, llm_concurrency: int):
        os.environ["RESEARCH_FETCH_CONCURRENCY"] = str(fetch_concurrency)
        os.environ["RESEARCH_LLM_CONCURRENCY"] = str(llm_concurrency)
        try:
            super().__init__(client=object(), llm_timeout_s=10.0)
        finally:
            del os.environ["RESEARCH_FETCH_CONCURRENCY"]
            del os.environ["RESEARCH_LLM_CONCURRENCY"]
        # Force the responses.parse capability flag on so the early-exit
        # fallback in _enrich_single_school doesn't short-circuit us.
        self.has_responses_parse = True

        self.fetch_in_flight = 0
        self.fetch_peak = 0
        self.llm_in_flight = 0
        self.llm_peak = 0
        self._lock = asyncio.Lock()

    async def _gather_evidence(self, school, player_stats, trusted_domains):
        async with self._lock:
            self.fetch_in_flight += 1
            self.fetch_peak = max(self.fetch_peak, self.fetch_in_flight)
        try:
            # Block long enough that several siblings can pile up if the
            # cap is broken.
            await asyncio.sleep(0.02)
            return _evidence()
        finally:
            async with self._lock:
                self.fetch_in_flight -= 1

    async def _review_school(
        self, school, player_stats, baseball_assessment, academic_score,
        evidence, talking_points,
    ):
        async with self._lock:
            self.llm_in_flight += 1
            self.llm_peak = max(self.llm_peak, self.llm_in_flight)
        try:
            await asyncio.sleep(0.02)
            return _review()
        finally:
            async with self._lock:
                self.llm_in_flight -= 1


def _schools(n: int) -> List[Dict[str, Any]]:
    return [
        {"school_name": f"School {i}", "delta": float(n - i), "fit_label": "Fit"}
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_fanout_caps_fetch_concurrency():
    service = _CountingService(fetch_concurrency=2, llm_concurrency=10)

    await service.enrich_and_rerank(
        schools=_schools(8),
        player_stats={"primary_position": "SS"},
        baseball_assessment={"predicted_tier": "Non-D1"},
        academic_score={},
        final_limit=8,  # set so research_limit == len(schools_copy) → fan-out path
    )

    assert service.fetch_peak == 2, (
        f"fetch concurrency cap broken: peak={service.fetch_peak} expected=2"
    )


@pytest.mark.asyncio
async def test_fanout_caps_llm_concurrency():
    service = _CountingService(fetch_concurrency=10, llm_concurrency=3)

    await service.enrich_and_rerank(
        schools=_schools(8),
        player_stats={"primary_position": "SS"},
        baseball_assessment={"predicted_tier": "Non-D1"},
        academic_score={},
        final_limit=8,
    )

    assert service.llm_peak == 3, (
        f"llm concurrency cap broken: peak={service.llm_peak} expected=3"
    )


@pytest.mark.asyncio
async def test_fanout_processes_all_eligible_schools():
    """Sanity: every eligible school finishes a fetch+LLM pair under fan-out."""
    service = _CountingService(fetch_concurrency=3, llm_concurrency=10)

    ranked = await service.enrich_and_rerank(
        schools=_schools(6),
        player_stats={"primary_position": "SS"},
        baseball_assessment={"predicted_tier": "Non-D1"},
        academic_score={},
        final_limit=6,
    )

    assert len(ranked) == 6
    assert all(s["research_status"] in ("completed", "partial", "metadata_only") for s in ranked)


@pytest.mark.asyncio
async def test_batched_path_does_not_use_semaphores_when_max_schools_subset():
    """When max_schools < total and final_limit is None, the rank-aware
    batched path runs and semaphores stay None inside _enrich_single_school.
    Verified indirectly: fan-out's higher LLM cap (10) shouldn't be reached
    because batched-path concurrency is capped by batch_size."""
    os.environ["RESEARCH_FETCH_CONCURRENCY"] = "10"
    os.environ["RESEARCH_LLM_CONCURRENCY"] = "10"
    try:
        service = _CountingService.__new__(_CountingService)
        DeepSchoolInsightService.__init__(
            service,
            client=object(),
            initial_batch_size=2,
            batch_size=2,
            max_schools=4,
            llm_timeout_s=10.0,
        )
    finally:
        del os.environ["RESEARCH_FETCH_CONCURRENCY"]
        del os.environ["RESEARCH_LLM_CONCURRENCY"]
    service.has_responses_parse = True
    service.fetch_in_flight = 0
    service.fetch_peak = 0
    service.llm_in_flight = 0
    service.llm_peak = 0
    service._lock = asyncio.Lock()

    # 6 schools, max_schools=4, no final_limit → research_limit=4 < 6 → batched path.
    await service.enrich_and_rerank(
        schools=_schools(6),
        player_stats={"primary_position": "SS"},
        baseball_assessment={"predicted_tier": "Non-D1"},
        academic_score={},
        # no final_limit
    )

    # Peak fetch concurrency under batched path is bounded by batch_size (2),
    # NOT by RESEARCH_FETCH_CONCURRENCY (10). So if batched path is correctly
    # taken, peak stays at 2.
    assert service.fetch_peak <= 2, (
        f"batched-path fetch concurrency expected ≤ batch_size=2, got {service.fetch_peak}"
    )
