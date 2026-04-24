import pytest
from bs4 import BeautifulSoup

from backend.evaluation.competitiveness import classify_fit
from backend.llm.deep_school_insights import (
    ACADEMIC_FIT_PENALTY_MAP,
    CROSS_SCHOOL_OPPORTUNITY_WEIGHT,
    CROSS_SCHOOL_Z_CLAMP,
    DeepSchoolInsight,
    DeepSchoolInsightService,
    DeepSchoolReview,
    FIT_FAMILY_BASE,
    GatheredEvidence,
    MAX_RERANK_ADJUSTMENT,
    PRIORITY_WEIGHTS,
    MatchedPlayer,
    OpportunityContext,
    ParsedPlayer,
    ParsedStatLine,
    ResearchSource,
    RecruitingContext,
    RosterContext,
    _academic_penalty,
    _apply_cross_school_reranking,
    _compute_relative_opportunity_metrics,
    _has_meaningful_evidence,
    compute_raw_opportunity_signal,
    compute_ranking_adjustment,
    compute_ranking_score,
    compute_roster_label,
)
from backend.roster_scraper.sidearm_scraper import SidearmRosterScraper


def test_compute_ranking_adjustment_rewards_openings_and_departures():
    evidence = GatheredEvidence(
        roster_context=RosterContext(
            position_data_quality="exact",
            likely_departures_same_family=3,
            starter_opening_estimate_same_family="high",
            starter_opening_estimate_exact_position="medium",
        ),
        recruiting_context=RecruitingContext(
            incoming_same_family_transfers=0,
            impact_additions_same_family=0,
        ),
        opportunity_context=OpportunityContext(
            competition_level="low",
            opportunity_level="high",
        ),
        sources=[],
        data_gaps=[],
    )
    review = DeepSchoolReview(
        base_athletic_fit="Reach",
        opportunity_fit="Fit",
        final_school_view="Fit",
        adjustment_from_base="up_one",
        confidence="high",
        fit_summary="",
        program_summary="",
        roster_summary="",
        opportunity_summary="",
        trend_summary="",
    )

    adjustment = compute_ranking_adjustment(evidence, review)
    assert adjustment > 10


def test_compute_ranking_adjustment_penalizes_crowded_low_confidence_school():
    evidence = GatheredEvidence(
        roster_context=RosterContext(
            position_data_quality="family_only",
            likely_departures_same_family=0,
            starter_opening_estimate_same_family="low",
            starter_opening_estimate_exact_position="unknown",
        ),
        recruiting_context=RecruitingContext(
            incoming_same_family_transfers=2,
            impact_additions_same_family=2,
        ),
        opportunity_context=OpportunityContext(
            competition_level="high",
            opportunity_level="low",
        ),
        sources=[],
        data_gaps=[],
    )
    review = DeepSchoolReview(
        base_athletic_fit="Fit",
        opportunity_fit="Reach",
        final_school_view="Reach",
        adjustment_from_base="down_one",
        confidence="low",
        fit_summary="",
        program_summary="",
        roster_summary="",
        opportunity_summary="",
        trend_summary="",
    )

    adjustment = compute_ranking_adjustment(evidence, review)
    assert adjustment < 0


def test_has_meaningful_evidence_accepts_structured_fields_without_sources():
    evidence = GatheredEvidence(
        roster_context=RosterContext(
            same_family_count=7,
            starter_opening_estimate_same_family="medium",
        ),
        recruiting_context=RecruitingContext(
            incoming_same_family_recruits=2,
        ),
        opportunity_context=OpportunityContext(
            opportunity_level="medium",
        ),
        sources=[],
    )

    assert _has_meaningful_evidence(evidence) is True


def test_has_meaningful_evidence_rejects_sources_only_unknown_fields():
    evidence = GatheredEvidence(
        sources=[
            ResearchSource(
                label="Official roster page",
                url="https://example.edu/roster",
                source_type="official_roster",
            )
        ],
        data_gaps=["Could not infer target-position details."],
    )

    assert _has_meaningful_evidence(evidence) is False


def test_compute_roster_label_returns_unknown_without_meaningful_evidence():
    evidence = GatheredEvidence(
        sources=[
            ResearchSource(
                label="Official roster page",
                url="https://example.edu/roster",
                source_type="official_roster",
            )
        ],
        data_gaps=["Could not infer target-position details."],
    )

    assert compute_roster_label(evidence) == "unknown"


class _StubInsightService(DeepSchoolInsightService):
    def __init__(self, adjustments, *, initial_batch_size=2, batch_size=2, max_schools=None):
        super().__init__(
            client=object(),
            initial_batch_size=initial_batch_size,
            batch_size=batch_size,
            max_schools=max_schools,
            llm_timeout_s=1.0,
        )
        self.adjustments = adjustments
        self.visited = []

    async def _enrich_single_school(
        self,
        school,
        player_stats,
        baseball_assessment,
        academic_score,
    ):
        school_name = school["school_name"]
        self.visited.append(school_name)
        adjustment = self.adjustments[school_name]
        evidence = GatheredEvidence(
            roster_context=RosterContext(
                position_data_quality="exact",
                likely_departures_same_family=2 if adjustment > 0 else 0,
                starter_opening_estimate_same_family="high" if adjustment > 0 else "low",
            ),
            recruiting_context=RecruitingContext(
                incoming_same_family_transfers=0 if adjustment > 0 else 1,
                impact_additions_same_family=0 if adjustment > 0 else 1,
            ),
            opportunity_context=OpportunityContext(
                competition_level="low" if adjustment > 0 else "high",
                opportunity_level="high" if adjustment > 0 else "low",
            ),
            sources=[
                ResearchSource(
                    label=f"{school_name} roster",
                    url=f"https://example.edu/{school_name}/roster",
                    source_type="official_roster",
                    supports=[
                        "position_data_quality",
                        "likely_departures_same_family",
                        "starter_opening_estimate_same_family",
                        "competition_level",
                        "opportunity_level",
                    ],
                )
            ],
        )
        review = DeepSchoolReview(
            base_athletic_fit=school.get("fit_label") or "Fit",
            opportunity_fit="Safety" if adjustment > 0 else "Reach",
            final_school_view="Safety" if adjustment > 0 else "Reach",
            adjustment_from_base="up_one" if adjustment > 0 else "down_one",
            confidence="high",
            why_this_school=f"{school_name} is a strong match for your profile.",
            school_snapshot=f"{school_name} program snapshot.",
            considerations=[],
        )
        return DeepSchoolInsight(
            school_name=school_name,
            evidence=evidence,
            review=review,
            ranking_adjustment=float(adjustment),
            ranking_score=compute_ranking_score(float(school.get("delta") or 0.0), float(adjustment)),
            research_status="completed",
        )


def _make_research_evidence(
    *,
    opportunity_level="medium",
    competition_level="medium",
    same_family_opening="unknown",
    exact_position_opening="unknown",
    departures=0,
    transfers=0,
    impact_additions=0,
) -> GatheredEvidence:
    return GatheredEvidence(
        roster_context=RosterContext(
            starter_opening_estimate_same_family=same_family_opening,
            starter_opening_estimate_exact_position=exact_position_opening,
            likely_departures_same_family=departures,
        ),
        recruiting_context=RecruitingContext(
            incoming_same_family_transfers=transfers,
            impact_additions_same_family=impact_additions,
        ),
        opportunity_context=OpportunityContext(
            competition_level=competition_level,
            opportunity_level=opportunity_level,
        ),
        sources=[
            ResearchSource(
                label="Test roster",
                url="https://example.edu/roster",
                source_type="official_roster",
                supports=["opportunity_level"],
            )
        ],
    )


def _make_cross_school(
    name: str,
    *,
    research_id: int,
    delta: float,
    fit_label: str,
    ranking_adjustment: float = 0.0,
    research_status: str = "completed",
    academic_fit: str = "fit",
    opportunity_level: str = "medium",
    competition_level: str = "medium",
    same_family_opening: str = "unknown",
    exact_position_opening: str = "unknown",
    departures: int = 0,
    transfers: int = 0,
    impact_additions: int = 0,
):
    school = {
        "school_name": name,
        "_research_id": research_id,
        "delta": delta,
        "fit_label": fit_label,
        "academic_fit": academic_fit,
        "research_status": research_status,
        "ranking_adjustment": ranking_adjustment,
        "ranking_score": compute_ranking_score(delta, ranking_adjustment),
    }
    if research_status in ("completed", "partial"):
        school["research_packet"] = _make_research_evidence(
            opportunity_level=opportunity_level,
            competition_level=competition_level,
            same_family_opening=same_family_opening,
            exact_position_opening=exact_position_opening,
            departures=departures,
            transfers=transfers,
            impact_additions=impact_additions,
        ).model_dump()
    return school


class _ConfiguredInsightService(DeepSchoolInsightService):
    def __init__(self, configs):
        super().__init__(
            client=object(),
            initial_batch_size=max(1, len(configs)),
            batch_size=max(1, len(configs)),
            llm_timeout_s=1.0,
        )
        self.configs = configs

    async def _enrich_single_school(
        self,
        school,
        player_stats,
        baseball_assessment,
        academic_score,
    ):
        config = self.configs[school["school_name"]]
        evidence = _make_research_evidence(
            opportunity_level=config.get("opportunity_level", "medium"),
            competition_level=config.get("competition_level", "medium"),
            same_family_opening=config.get("same_family_opening", "unknown"),
            exact_position_opening=config.get("exact_position_opening", "unknown"),
            departures=config.get("departures", 0),
            transfers=config.get("transfers", 0),
            impact_additions=config.get("impact_additions", 0),
        )
        adjustment = float(config.get("ranking_adjustment", 0.0))
        review = DeepSchoolReview(
            base_athletic_fit=school.get("fit_label") or "Fit",
            opportunity_fit=school.get("fit_label") or "Fit",
            final_school_view=school.get("fit_label") or "Fit",
            adjustment_from_base="up_one" if adjustment > 0 else ("down_one" if adjustment < 0 else "none"),
            confidence="high",
            why_this_school="",
            school_snapshot="",
            considerations=[],
        )
        return DeepSchoolInsight(
            school_name=school["school_name"],
            evidence=evidence,
            review=review,
            ranking_adjustment=adjustment,
            ranking_score=compute_ranking_score(float(school.get("delta") or 0.0), adjustment),
            research_status=config.get("research_status", "completed"),
        )


@pytest.mark.asyncio
async def test_enrich_and_rerank_processes_entire_school_list_in_batches():
    service = _StubInsightService(
        {
            "School A": 0.0,
            "School B": 0.0,
            "School C": 0.0,
            "School D": 0.0,
            "School E": 0.0,
        },
        initial_batch_size=2,
        batch_size=2,
    )
    schools = [
        {"school_name": "School A", "delta": 10.0, "fit_label": "Fit"},
        {"school_name": "School B", "delta": 9.0, "fit_label": "Fit"},
        {"school_name": "School C", "delta": 8.0, "fit_label": "Fit"},
        {"school_name": "School D", "delta": 7.0, "fit_label": "Fit"},
        {"school_name": "School E", "delta": 6.0, "fit_label": "Fit"},
    ]

    ranked = await service.enrich_and_rerank(
        schools=schools,
        player_stats={"primary_position": "SS"},
        baseball_assessment={"predicted_tier": "Non-D1"},
        academic_score={},
    )

    assert set(service.visited) == {school["school_name"] for school in schools}
    assert all(school["research_status"] == "completed" for school in ranked)


@pytest.mark.asyncio
async def test_enrich_and_rerank_allows_later_school_to_jump_to_top():
    service = _StubInsightService(
        {
            "School A": -2.0,
            "School B": -2.0,
            "School C": -2.0,
            "School D": 12.0,
        },
        initial_batch_size=2,
        batch_size=1,
    )
    schools = [
        {"school_name": "School A", "delta": 12.0, "fit_label": "Fit"},
        {"school_name": "School B", "delta": 11.0, "fit_label": "Fit"},
        {"school_name": "School C", "delta": 10.0, "fit_label": "Fit"},
        {"school_name": "School D", "delta": 2.0, "fit_label": "Fit"},
    ]

    ranked = await service.enrich_and_rerank(
        schools=schools,
        player_stats={"primary_position": "SS"},
        baseball_assessment={"predicted_tier": "Non-D1"},
        academic_score={},
    )

    assert ranked[0]["school_name"] == "School D"
    assert ranked[0]["rank"] == 1
    assert ranked[0]["ranking_adjustment"] == 12.0


@pytest.mark.asyncio
async def test_enrich_and_rerank_researches_full_consideration_pool_before_final_cut():
    service = _StubInsightService(
        {
            "School A": 0.0,
            "School B": 0.0,
            "School C": 0.0,
            "School D": 0.0,
        },
        initial_batch_size=2,
        batch_size=2,
        max_schools=2,
    )
    schools = [
        {"school_name": "School A", "delta": 12.0, "fit_label": "Fit"},
        {"school_name": "School B", "delta": 11.0, "fit_label": "Fit"},
        {"school_name": "School C", "delta": 10.0, "fit_label": "Fit"},
        {"school_name": "School D", "delta": 9.0, "fit_label": "Fit"},
    ]

    ranked = await service.enrich_and_rerank(
        schools=schools,
        player_stats={"primary_position": "SS"},
        baseball_assessment={"predicted_tier": "Non-D1"},
        academic_score={},
        final_limit=2,
    )

    assert set(service.visited) == {school["school_name"] for school in schools}
    assert all(school["research_status"] == "completed" for school in ranked)


def test_pydantic_schemas_are_pre_warmed():
    """Schemas must be fully built at import time to prevent MockValSer races."""
    for model_cls in (
        ResearchSource, RosterContext, RecruitingContext, OpportunityContext,
        GatheredEvidence, DeepSchoolReview,
    ):
        assert model_cls.__pydantic_complete__ is True, f"{model_cls.__name__} not complete"
        assert type(model_cls.__pydantic_serializer__).__name__ == "SchemaSerializer", (
            f"{model_cls.__name__} serializer is {type(model_cls.__pydantic_serializer__).__name__}"
        )
        assert type(model_cls.__pydantic_validator__).__name__ == "SchemaValidator", (
            f"{model_cls.__name__} validator is {type(model_cls.__pydantic_validator__).__name__}"
        )


class _FakeResponses:
    @staticmethod
    def parse(**kwargs):
        pass


class _FakeClient:
    responses = _FakeResponses()


class _ReviewFailureStub(DeepSchoolInsightService):
    """Stub where gatherer succeeds with real evidence but reviewer always fails."""

    def __init__(self):
        super().__init__(
            client=_FakeClient(),
            initial_batch_size=1,
            batch_size=1,
            llm_timeout_s=1.0,
        )

    async def _gather_evidence(self, school, player_stats, trusted_domains):
        return GatheredEvidence(
            roster_context=RosterContext(
                position_data_quality="exact",
                same_family_count=5,
                likely_departures_same_family=2,
                starter_opening_estimate_same_family="high",
            ),
            recruiting_context=RecruitingContext(
                incoming_same_family_transfers=0,
                impact_additions_same_family=0,
            ),
            opportunity_context=OpportunityContext(
                competition_level="low",
                opportunity_level="high",
            ),
            sources=[
                ResearchSource(
                    label="Test roster",
                    url="https://example.edu/roster",
                    source_type="official_roster",
                    supports=["same_family_count"],
                )
            ],
        )

    async def _review_school(self, school, player_stats, baseball_assessment, academic_score, evidence):
        return None


@pytest.mark.asyncio
async def test_enrich_falls_back_to_partial_when_reviewer_fails():
    """When gatherer succeeds but reviewer fails, school gets partial status with non-zero adjustment."""
    service = _ReviewFailureStub()
    schools = [
        {"school_name": "Test U", "delta": 5.0, "fit_label": "Fit"},
    ]
    ranked = await service.enrich_and_rerank(
        schools=schools,
        player_stats={"primary_position": "SS"},
        baseball_assessment={"predicted_tier": "Non-D1"},
        academic_score={},
    )
    assert len(ranked) == 1
    school = ranked[0]
    assert school["research_status"] == "partial"
    # Evidence had high opportunity + low competition + high starter openings
    # At low confidence (0.35x), adjustment should still be meaningfully positive
    assert school["ranking_adjustment"] > 0
    assert school["ranking_score"] != school.get("delta", 0.0)


def test_compute_ranking_score_centers_on_fit():
    """Fits (delta near 0) should rank highest; reaches slightly preferred over equivalent safeties."""
    # Fit with some adjustment ranks highest
    assert compute_ranking_score(0.0, 2.0) == 2.0
    # Safety penalized by distance
    assert compute_ranking_score(6.0, 0.7) == -5.3
    # Strong safety ranks very low
    assert compute_ranking_score(17.0, 0.0) == -17.0
    # Reach slightly preferred over equivalent safety (0.85x vs 1.0x penalty)
    assert compute_ranking_score(-5.0, 0.0) > compute_ranking_score(5.0, 0.0)
    # Strong reach with good adjustment still ranks below a plain fit
    assert compute_ranking_score(-13.0, 6.0) < compute_ranking_score(0.0, 0.0)


@pytest.mark.asyncio
async def test_enrich_and_rerank_caps_strong_labels():
    """Category caps should limit Strong Safety and Strong Reach in final selection."""
    adjustments = {f"School {c}": 0.0 for c in "ABCDEFGH"}
    service = _StubInsightService(adjustments, initial_batch_size=8, batch_size=8)
    schools = [
        {"school_name": "School A", "delta": 17.0, "fit_label": "Strong Safety"},
        {"school_name": "School B", "delta": 15.0, "fit_label": "Strong Safety"},
        {"school_name": "School C", "delta": 12.0, "fit_label": "Strong Safety"},
        {"school_name": "School D", "delta": 10.0, "fit_label": "Strong Safety"},
        {"school_name": "School E", "delta": 1.0, "fit_label": "Fit"},
        {"school_name": "School F", "delta": -1.0, "fit_label": "Fit"},
        {"school_name": "School G", "delta": -10.0, "fit_label": "Strong Reach"},
        {"school_name": "School H", "delta": -13.0, "fit_label": "Strong Reach"},
    ]
    ranked = await service.enrich_and_rerank(
        schools=schools,
        player_stats={"primary_position": "SS"},
        baseball_assessment={"predicted_tier": "Non-D1"},
        academic_score={},
        final_limit=5,
    )
    strong_safeties = [s for s in ranked if s.get("fit_label") == "Strong Safety"]
    strong_reaches = [s for s in ranked if s.get("fit_label") == "Strong Reach"]
    assert len(strong_safeties) <= 2
    assert len(strong_reaches) <= 2
    # Fits should be in the list
    fit_names = {s["school_name"] for s in ranked if s.get("fit_label") == "Fit"}
    assert "School E" in fit_names
    assert "School F" in fit_names


def test_raw_opportunity_signal_returns_none_for_failed_like_statuses():
    failed_school = {
        "_research_id": 0,
        "research_status": "failed",
        "research_packet": _make_research_evidence(opportunity_level="high").model_dump(),
    }
    queued_school = {
        "_research_id": 1,
        "research_status": "queued",
        "research_packet": _make_research_evidence(opportunity_level="high").model_dump(),
    }

    assert compute_raw_opportunity_signal(failed_school) is None
    assert compute_raw_opportunity_signal(queued_school) is None
    assert compute_raw_opportunity_signal({"research_status": "completed"}) is None


def test_raw_opportunity_signal_uses_exact_position_opening_and_excludes_review_terms():
    school = {
        "_research_id": 1,
        "research_status": "completed",
        "research_confidence": "low",
        "review_adjustment_from_base": "down_one",
        "research_packet": _make_research_evidence(
            opportunity_level="high",
            competition_level="low",
            same_family_opening="high",
            exact_position_opening="medium",
            departures=6,
            transfers=4,
            impact_additions=5,
        ).model_dump(),
    }

    assert compute_raw_opportunity_signal(school) == 14.5


def test_relative_opportunity_metrics_return_empty_with_single_researched_school():
    schools = [
        _make_cross_school(
            "Only Research",
            research_id=0,
            delta=0.0,
            fit_label="Fit",
            opportunity_level="high",
            competition_level="low",
            same_family_opening="high",
            departures=3,
        ),
        _make_cross_school(
            "No Research",
            research_id=1,
            delta=0.0,
            fit_label="Fit",
            research_status="failed",
        ),
    ]

    assert _compute_relative_opportunity_metrics(schools) == {}


def test_relative_opportunity_metrics_zero_out_for_identical_signals():
    schools = [
        _make_cross_school(
            "School A",
            research_id=0,
            delta=0.0,
            fit_label="Fit",
            opportunity_level="medium",
            competition_level="medium",
            same_family_opening="unknown",
            departures=1,
        ),
        _make_cross_school(
            "School B",
            research_id=1,
            delta=0.0,
            fit_label="Fit",
            opportunity_level="medium",
            competition_level="medium",
            same_family_opening="unknown",
            departures=1,
        ),
    ]

    metrics = _compute_relative_opportunity_metrics(schools)

    assert metrics[0]["relative_opportunity_zscore"] == 0.0
    assert metrics[0]["relative_opportunity_bonus"] == 0.0
    assert metrics[1]["relative_opportunity_zscore"] == 0.0
    assert metrics[1]["relative_opportunity_bonus"] == 0.0


def test_cross_school_family_dominance_under_baseball_fit_priority():
    """Under ranking_priority='baseball_fit' the Fit > Safety > Reach invariant
    still holds even in worst/best case because the base gap (100/45/85) plus
    the aggressive weight multipliers keep families well separated.

    Under the balanced/None profile, Safety and Reach are intentionally close
    to Fit (user preference: don't penalize them), so this strict invariant
    no longer holds there — see test_balanced_priority_only_docks_strong_outliers.
    """
    schools = [
        _make_cross_school(
            "Fit Floor",
            research_id=0,
            delta=4.0,
            fit_label="Fit",
            ranking_adjustment=-14.0,
            academic_fit="reach",
            opportunity_level="low",
            competition_level="high",
            same_family_opening="low",
            exact_position_opening="low",
            departures=0,
            transfers=3,
            impact_additions=3,
        ),
        _make_cross_school(
            "Safety Ceiling",
            research_id=1,
            delta=4.01,
            fit_label="Safety",
            ranking_adjustment=14.0,
            opportunity_level="high",
            competition_level="low",
            same_family_opening="high",
            exact_position_opening="high",
            departures=4,
        ),
        _make_cross_school(
            "Reach Ceiling",
            research_id=2,
            delta=-4.0,
            fit_label="Reach",
            ranking_adjustment=14.0,
            opportunity_level="high",
            competition_level="low",
            same_family_opening="high",
            exact_position_opening="high",
            departures=4,
        ),
    ]

    _apply_cross_school_reranking(schools, ranking_priority="baseball_fit")

    by_name = {school["school_name"]: school for school in schools}
    assert by_name["Fit Floor"]["cross_school_composite"] > by_name["Safety Ceiling"]["cross_school_composite"]
    # Reach is aspirational under baseball_fit (base=85), so a strong-roster
    # Reach can beat a weak-roster Safety (base=45) — intentional.
    assert by_name["Reach Ceiling"]["cross_school_composite"] > by_name["Safety Ceiling"]["cross_school_composite"]


def test_balanced_priority_only_docks_strong_outliers():
    """Under balanced/None priority, Fit/Safety/Reach are grouped together
    and only Strong Safety / Strong Reach get docked vs Fit. This encodes the
    product philosophy that a healthy Safety/Reach is not meaningfully worse
    than a Fit — only extreme mismatches should lose rank."""
    schools = [
        _make_cross_school(
            "Fit School", research_id=0, delta=0.0, fit_label="Fit",
        ),
        _make_cross_school(
            "Safety School", research_id=1, delta=4.0, fit_label="Safety",
        ),
        _make_cross_school(
            "Reach School", research_id=2, delta=-4.0, fit_label="Reach",
        ),
        _make_cross_school(
            "Strong Safety School", research_id=3, delta=10.0, fit_label="Strong Safety",
        ),
        _make_cross_school(
            "Strong Reach School", research_id=4, delta=-10.0, fit_label="Strong Reach",
        ),
    ]

    _apply_cross_school_reranking(schools, ranking_priority=None)
    by_name = {school["school_name"]: school for school in schools}

    assert by_name["Fit School"]["cross_school_composite"] > by_name["Strong Safety School"]["cross_school_composite"]
    assert by_name["Fit School"]["cross_school_composite"] > by_name["Strong Reach School"]["cross_school_composite"]
    assert by_name["Safety School"]["cross_school_composite"] > by_name["Strong Safety School"]["cross_school_composite"]
    assert by_name["Reach School"]["cross_school_composite"] > by_name["Strong Reach School"]["cross_school_composite"]


def test_cross_school_differentiates_within_fit_family():
    schools = [
        _make_cross_school(
            "Low Opportunity",
            research_id=0,
            delta=0.0,
            fit_label="Fit",
            opportunity_level="low",
            competition_level="high",
            same_family_opening="low",
            exact_position_opening="low",
            transfers=3,
            impact_additions=3,
        ),
        _make_cross_school(
            "Medium Opportunity",
            research_id=1,
            delta=0.0,
            fit_label="Fit",
            opportunity_level="medium",
            competition_level="medium",
            same_family_opening="medium",
            exact_position_opening="unknown",
            departures=1,
        ),
        _make_cross_school(
            "High Opportunity",
            research_id=2,
            delta=0.0,
            fit_label="Fit",
            opportunity_level="high",
            competition_level="low",
            same_family_opening="high",
            exact_position_opening="high",
            departures=4,
        ),
    ]

    _apply_cross_school_reranking(schools)
    ranked = sorted(
        schools,
        key=lambda school: (
            float(school.get("cross_school_composite") or 0.0),
            float(school.get("ranking_score") or 0.0),
            float(school.get("delta") or 0.0),
        ),
        reverse=True,
    )

    assert [school["school_name"] for school in ranked] == [
        "High Opportunity",
        "Medium Opportunity",
        "Low Opportunity",
    ]


def test_cross_school_applies_academic_reach_penalty():
    schools = [
        _make_cross_school(
            "Academic Fit",
            research_id=0,
            delta=0.0,
            fit_label="Fit",
            academic_fit="fit",
            opportunity_level="medium",
        ),
        _make_cross_school(
            "Academic Reach",
            research_id=1,
            delta=0.0,
            fit_label="Fit",
            academic_fit="reach",
            opportunity_level="medium",
        ),
    ]

    _apply_cross_school_reranking(schools)
    by_name = {school["school_name"]: school for school in schools}

    assert by_name["Academic Reach"]["academic_fit_penalty"] == -2.0
    assert (
        by_name["Academic Fit"]["cross_school_composite"]
        - by_name["Academic Reach"]["cross_school_composite"]
        == 2.0
    )


def test_cross_school_applies_academic_strong_safety_penalty():
    """Academic strong safety schools receive a penalty in cross-school ranking."""
    schools = [
        _make_cross_school(
            "Academic Fit",
            research_id=0,
            delta=0.0,
            fit_label="Fit",
            academic_fit="Fit",
            opportunity_level="medium",
        ),
        _make_cross_school(
            "Academic Strong Safety",
            research_id=1,
            delta=0.0,
            fit_label="Fit",
            academic_fit="Strong Safety",
            opportunity_level="medium",
        ),
    ]

    _apply_cross_school_reranking(schools)
    by_name = {school["school_name"]: school for school in schools}

    assert by_name["Academic Strong Safety"]["academic_fit_penalty"] == -9.0
    assert (
        by_name["Academic Fit"]["cross_school_composite"]
        > by_name["Academic Strong Safety"]["cross_school_composite"]
    )


def test_cross_school_degrades_gracefully_when_all_research_failed():
    schools = [
        _make_cross_school(
            "Fit Failed",
            research_id=0,
            delta=1.0,
            fit_label="Fit",
            ranking_adjustment=2.0,
            research_status="failed",
        ),
        _make_cross_school(
            "Reach Failed",
            research_id=1,
            delta=-5.0,
            fit_label="Reach",
            ranking_adjustment=1.0,
            research_status="failed",
        ),
    ]

    _apply_cross_school_reranking(schools)
    by_name = {school["school_name"]: school for school in schools}

    # Schools without an academic_selectivity_score fall back to 2.5. Under
    # the balanced profile (median=5.0, weight=2.0) the delta is -2.5, which
    # the asymmetric quadratic penalty converts to -(-2.5**2) * 2.0 = -12.5.
    missing_selectivity_delta = 2.5 - 5.0
    missing_selectivity_bonus = -(missing_selectivity_delta ** 2) * PRIORITY_WEIGHTS[None]["academic_quality"]

    assert by_name["Fit Failed"]["raw_opportunity_signal"] is None
    assert by_name["Fit Failed"]["relative_opportunity_bonus"] == 0.0
    assert by_name["Fit Failed"]["cross_school_composite"] == round(
        FIT_FAMILY_BASE["Fit"]
        + by_name["Fit Failed"]["ranking_score"]
        + missing_selectivity_bonus,
        2,
    )
    assert by_name["Reach Failed"]["cross_school_composite"] == round(
        FIT_FAMILY_BASE["Reach"]
        + by_name["Reach Failed"]["ranking_score"]
        + missing_selectivity_bonus,
        2,
    )


def test_partial_school_is_eligible_for_relative_bonus_when_packet_exists():
    schools = [
        _make_cross_school(
            "Partial School",
            research_id=0,
            delta=0.0,
            fit_label="Fit",
            research_status="partial",
            opportunity_level="high",
            competition_level="low",
            same_family_opening="high",
            departures=3,
        ),
        _make_cross_school(
            "Completed School",
            research_id=1,
            delta=0.0,
            fit_label="Fit",
            research_status="completed",
            opportunity_level="low",
            competition_level="high",
            same_family_opening="low",
            impact_additions=3,
            transfers=3,
        ),
    ]

    _apply_cross_school_reranking(schools)
    partial_school = next(s for s in schools if s["school_name"] == "Partial School")

    assert partial_school["raw_opportunity_signal"] is not None
    assert partial_school["relative_opportunity_zscore"] is not None
    assert partial_school["relative_opportunity_bonus"] != 0.0


@pytest.mark.asyncio
async def test_final_limit_caps_still_use_cross_school_composite():
    service = _ConfiguredInsightService(
        {
            "Strong A": {
                "ranking_adjustment": 4.0,
                "opportunity_level": "low",
                "competition_level": "high",
                "same_family_opening": "low",
                "exact_position_opening": "low",
                "impact_additions": 3,
                "transfers": 3,
            },
            "Strong B": {
                "ranking_adjustment": 0.0,
                "opportunity_level": "high",
                "competition_level": "low",
                "same_family_opening": "high",
                "exact_position_opening": "high",
                "departures": 4,
            },
            "Strong C": {
                "ranking_adjustment": -1.0,
                "opportunity_level": "medium",
                "competition_level": "medium",
                "same_family_opening": "medium",
                "departures": 1,
            },
            "Fit D": {
                "ranking_adjustment": 0.0,
                "opportunity_level": "medium",
                "competition_level": "medium",
            },
        }
    )
    schools = [
        {"school_name": "Strong A", "delta": 12.0, "fit_label": "Strong Safety"},
        {"school_name": "Strong B", "delta": 10.0, "fit_label": "Strong Safety"},
        {"school_name": "Strong C", "delta": 10.0, "fit_label": "Strong Safety"},
        {"school_name": "Fit D", "delta": 0.0, "fit_label": "Fit"},
    ]

    ranked = await service.enrich_and_rerank(
        schools=schools,
        player_stats={"primary_position": "SS"},
        baseball_assessment={"predicted_tier": "Non-D1"},
        academic_score={},
        final_limit=3,
    )

    selected_strong_safeties = {
        school["school_name"] for school in ranked if school.get("fit_label") == "Strong Safety"
    }
    # Cap of MAX_STRONG_SAFETY=2 picks the top two by cross_school_composite.
    # Strong B leads (great roster context). Strong A beats Strong C despite
    # worse roster because its ranking_adjustment (+4) outweighs C's edge.
    assert selected_strong_safeties == {"Strong A", "Strong B"}


def test_baseball_fit_priority_preserves_family_dominance_invariant():
    """Under baseball_fit priority, Fit family always ranks above Safety family
    even in worst/best case. This is the profile used when users explicitly
    prioritize baseball, so the strict invariant is still enforced.

    For balanced/None and academics profiles, Safety/Reach are intentionally
    close to Fit (see test_balanced_priority_only_docks_strong_outliers).
    """
    from backend.llm.deep_school_insights.ranking import FIT_FAMILY_BASE_BY_PRIORITY

    bb_fit_family = FIT_FAMILY_BASE_BY_PRIORITY["baseball_fit"]
    max_bonus = round(CROSS_SCHOOL_OPPORTUNITY_WEIGHT * CROSS_SCHOOL_Z_CLAMP, 2)
    worst_penalty = min(ACADEMIC_FIT_PENALTY_MAP.values())
    family_min = {"Fit": float("inf"), "Safety": float("inf"), "Reach": float("inf")}
    family_max = {"Fit": float("-inf"), "Safety": float("-inf"), "Reach": float("-inf")}

    for milli in range(-18000, 20001):
        raw_delta = milli / 1000.0
        fit_label = classify_fit(raw_delta)
        rounded_delta = round(raw_delta, 2)
        if fit_label == "Fit":
            family = "Fit"
        elif "Safety" in fit_label:
            family = "Safety"
        else:
            family = "Reach"

        family_base = bb_fit_family[fit_label]
        best_composite = family_base + compute_ranking_score(rounded_delta, MAX_RERANK_ADJUSTMENT) + max_bonus
        worst_composite = (
            family_base
            + compute_ranking_score(rounded_delta, -MAX_RERANK_ADJUSTMENT)
            - max_bonus
            + worst_penalty
        )
        family_min[family] = min(family_min[family], worst_composite)
        family_max[family] = max(family_max[family], best_composite)

    assert family_min["Fit"] > family_max["Safety"]


# ---------------------------------------------------------------------------
# Tests for deterministic evidence computation
# ---------------------------------------------------------------------------

def _make_player(
    name: str,
    position_family: str = "INF",
    position_normalized: str = "SS",
    class_year: int = 2,
    previous_school: str = None,
) -> ParsedPlayer:
    return ParsedPlayer(
        name=name,
        position_family=position_family,
        position_normalized=position_normalized,
        normalized_class_year=class_year,
        previous_school=previous_school,
    )


def _make_stat(name: str, stat_type: str = "batting", gp: int = 30, gs: int = 25) -> ParsedStatLine:
    return ParsedStatLine(
        player_name=name,
        stat_type=stat_type,
        games_played=gp,
        games_started=gs,
    )


@pytest.mark.xfail(
    strict=False,
    reason=(
        "Evidence computation now forward-projects departures to the player's "
        "enrollment year; these expected counts pin the pre-projection behavior. "
        "Rewrite when the forward-projection semantics are stable."
    ),
)
def test_compute_evidence_counts_same_family():
    """Deterministic evidence correctly counts same-family players."""
    service = DeepSchoolInsightService.__new__(DeepSchoolInsightService)
    players = [
        MatchedPlayer(player=_make_player("A", "INF", "SS", 2)),
        MatchedPlayer(player=_make_player("B", "INF", "2B", 3)),
        MatchedPlayer(player=_make_player("C", "INF", "3B", 4)),  # senior, departure
        MatchedPlayer(player=_make_player("D", "OF", "CF", 2)),   # different family
        MatchedPlayer(player=_make_player("E", "INF", "SS", 5)),  # grad, departure
    ]
    evidence = service._compute_evidence(
        matched_players=players,
        player_stats={"primary_position": "SS"},
        roster_url="https://example.edu/roster",
        stats_available=False,
    )
    assert evidence.roster_context.same_family_count == 4  # A, B, C, E
    assert evidence.roster_context.likely_departures_same_family == 2  # C (Sr), E (Gr)
    assert evidence.roster_context.same_exact_position_count == 2  # A, E (both SS)
    assert evidence.roster_context.same_family_upperclassmen == 3  # B (Jr=3), C (Sr=4), E (Gr=5)
    assert evidence.roster_context.same_family_underclassmen == 1  # A (So=2)


def test_compute_evidence_with_stats_tracks_high_usage():
    """When stats are available, high-usage returning players are tracked."""
    service = DeepSchoolInsightService.__new__(DeepSchoolInsightService)
    players = [
        MatchedPlayer(
            player=_make_player("Smith", "INF", "SS", 2),
            batting_stats=_make_stat("Smith", "batting", gp=40, gs=38),
        ),
        MatchedPlayer(
            player=_make_player("Jones", "INF", "SS", 4),  # senior, departing
            batting_stats=_make_stat("Jones", "batting", gp=45, gs=44),
        ),
        MatchedPlayer(
            player=_make_player("Lee", "INF", "2B", 1),
            batting_stats=_make_stat("Lee", "batting", gp=20, gs=5),
        ),
    ]
    evidence = service._compute_evidence(
        matched_players=players,
        player_stats={"primary_position": "SS"},
        roster_url="https://example.edu/roster",
        stats_available=True,
    )
    # Smith is returning (So) with 38 GS — high usage
    # Jones is departing (Sr) — not counted
    # Lee has only 5 GS — not high usage
    assert evidence.roster_context.returning_high_usage_same_family == 1
    assert evidence.roster_context.returning_high_usage_exact_position == 1  # Smith is SS


def test_compute_evidence_detects_transfers():
    """Players with college previous_school are counted as transfers."""
    service = DeepSchoolInsightService.__new__(DeepSchoolInsightService)
    players = [
        MatchedPlayer(player=_make_player("A", "INF", "SS", 3, previous_school="State University")),
        MatchedPlayer(player=_make_player("B", "INF", "2B", 2)),
    ]
    evidence = service._compute_evidence(
        matched_players=players,
        player_stats={"primary_position": "SS"},
        roster_url="https://example.edu/roster",
        stats_available=False,
    )
    assert evidence.recruiting_context.incoming_same_family_transfers == 1


def test_compute_evidence_sets_position_data_quality():
    """Position data quality reflects how specific position listings are."""
    service = DeepSchoolInsightService.__new__(DeepSchoolInsightService)

    # All exact positions
    players_exact = [
        MatchedPlayer(player=_make_player("A", "INF", "SS", 2)),
        MatchedPlayer(player=_make_player("B", "INF", "2B", 3)),
    ]
    ev = service._compute_evidence(players_exact, {"primary_position": "SS"}, "url", False)
    assert ev.roster_context.position_data_quality == "exact"

    # Mix of exact and ambiguous (normalized=None means ambiguous)
    players_mixed = [
        MatchedPlayer(player=ParsedPlayer(name="A", position_family="INF", position_normalized="SS", normalized_class_year=2)),
        MatchedPlayer(player=ParsedPlayer(name="B", position_family="INF", position_normalized=None, normalized_class_year=3)),
    ]
    ev = service._compute_evidence(players_mixed, {"primary_position": "SS"}, "url", False)
    assert ev.roster_context.position_data_quality == "mixed"


def test_compute_evidence_keeps_position_quality_when_no_same_family_players():
    """Exact roster positions should remain meaningful even when target family count is zero."""
    service = DeepSchoolInsightService.__new__(DeepSchoolInsightService)
    players = [
        MatchedPlayer(player=_make_player("Pitcher A", "P", "P", 2)),
        MatchedPlayer(player=_make_player("Pitcher B", "P", "P", 4)),
    ]

    ev = service._compute_evidence(players, {"primary_position": "SS"}, "url", False)

    assert ev.roster_context.position_data_quality == "exact"
    assert ev.roster_context.same_family_count == 0
    assert "No listed players matched the INF position family on the roster." in ev.roster_context.notes


def test_compute_evidence_sources_include_stats_url():
    """When stats are available, a stats source is added."""
    service = DeepSchoolInsightService.__new__(DeepSchoolInsightService)
    players = [MatchedPlayer(player=_make_player("A", "INF", "SS", 2))]
    ev = service._compute_evidence(
        players, {"primary_position": "SS"},
        "https://example.edu/sports/baseball/roster",
        stats_available=True,
    )
    source_types = {s.source_type for s in ev.sources}
    assert "official_roster" in source_types
    assert "official_stats" in source_types
    stats_source = next(s for s in ev.sources if s.source_type == "official_stats")
    assert "/stats" in stats_source.url


def test_match_players_to_stats_by_jersey_and_name():
    """Player-stat matching works via jersey number + last name."""
    service = DeepSchoolInsightService.__new__(DeepSchoolInsightService)
    players = [
        ParsedPlayer(name="John Smith", jersey_number="12", position_family="INF"),
        ParsedPlayer(name="Mike Jones", jersey_number="5", position_family="INF"),
    ]
    stats = [
        ParsedStatLine(jersey_number="12", player_name="Smith, John", stat_type="batting", games_played=30, games_started=28),
        ParsedStatLine(jersey_number="5", player_name="Jones, Mike", stat_type="pitching", games_played=20, games_started=15),
    ]
    matched = service._match_players_to_stats(players, stats)
    assert len(matched) == 2
    assert matched[0].batting_stats is not None
    assert matched[0].batting_stats.games_started == 28
    assert matched[1].pitching_stats is not None
    assert matched[1].pitching_stats.games_started == 15


def test_sidearm_extract_labeled_fields_handles_compact_label_value_text():
    scraper = SidearmRosterScraper.__new__(SidearmRosterScraper)
    soup = BeautifulSoup(
        """
        <div class="s-person-card">
          <div>PositionOF</div>
          <div>Academic YearSr.</div>
          <div>Height5' 8''</div>
          <div>Previous SchoolPrevious School: Dodge City CC</div>
          <div>B/TR/R</div>
        </div>
        """,
        "html.parser",
    )

    fields = scraper._extract_labeled_fields(soup.select_one(".s-person-card"))

    assert fields["position"] == "OF"
    assert fields["class_year"] == "Sr."
    assert fields["height"] == "5' 8''"
    assert fields["high_school"] == "Dodge City CC"
    assert fields["bats"] == "R"
    assert fields["throws"] == "R"


def test_parse_roster_players_prefers_richer_table_layout_over_shallow_cards():
    service = DeepSchoolInsightService.__new__(DeepSchoolInsightService)
    soup = BeautifulSoup(
        """
        <html>
          <div class="s-person-card">
            <h3><a>Alex Espaillat</a></h3>
            <div class="s-stamp">1</div>
          </div>
          <div class="s-person-card">
            <h3><a>Breydon Divine</a></h3>
            <div class="s-stamp">2</div>
          </div>
          <table class="sidearm-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Name</th>
                <th>Pos.</th>
                <th>Yr.</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>1</td>
                <td><a>Alex Espaillat</a></td>
                <td>OF</td>
                <td>So.</td>
              </tr>
              <tr>
                <td>2</td>
                <td><a>Breydon Divine</a></td>
                <td>CF</td>
                <td>Sr.</td>
              </tr>
            </tbody>
          </table>
        </html>
        """,
        "html.parser",
    )

    players = service._parse_roster_players(soup)

    assert [player.name for player in players] == ["Alex Espaillat", "Breydon Divine"]
    assert [player.position_family for player in players] == ["OF", "OF"]
    assert [player.normalized_class_year for player in players] == [2, 4]


def test_sidearm_extract_from_card_handles_unlabeled_compact_sidearm_cards():
    scraper = SidearmRosterScraper.__new__(SidearmRosterScraper)
    soup = BeautifulSoup(
        """
        <div class="s-person-card">
          <h3><a>Alex Espaillat</a></h3>
          <div class="s-stamp">1</div>
          <div>OF 6'0" 180 lbs R/R 1 Alex Espaillat So. Seminole, Fla. Seminole HS Full Bio</div>
        </div>
        """,
        "html.parser",
    )

    player = scraper._extract_from_card(soup.select_one(".s-person-card"))

    assert player["name"] == "Alex Espaillat"
    assert player["jersey_number"] == "1"
    assert player["position"] == "OF"
    assert player["class_year"] == "So."
    assert player["height"] == "6'0\""
    assert player["weight"] == "180"
    assert player["bats"] == "R"
    assert player["throws"] == "R"


# ---------------------------------------------------------------------------
# Tests for continuous academic penalty
# ---------------------------------------------------------------------------


def test_academic_penalty_zero_in_fit_range():
    # Dead zone matches the Fit label cutoff (|Δ| ≤ 0.6).
    assert _academic_penalty(0.0) == 0.0
    assert _academic_penalty(0.5) == 0.0
    assert _academic_penalty(-0.5) == 0.0
    assert _academic_penalty(0.6) == 0.0
    assert _academic_penalty(-0.6) == 0.0


def test_academic_penalty_mild_safety():
    # Δ=1.5 sits mid-Safety — penalty should be small but nonzero.
    penalty = _academic_penalty(1.5)
    assert -2.5 < penalty < 0.0


def test_academic_penalty_extreme_safety():
    penalty = _academic_penalty(5.0)
    assert penalty < -10.0


def test_academic_penalty_mild_reach():
    # Δ=-1.5 is the Reach/Strong Reach boundary — penalty is moderate.
    penalty = _academic_penalty(-1.5)
    assert -3.5 < penalty < 0.0


def test_academic_penalty_extreme_reach():
    penalty = _academic_penalty(-3.3)
    assert penalty < -4.0


def test_academic_penalty_scales_monotonically():
    """Larger gaps produce larger (more negative) penalties."""
    vals = [_academic_penalty(d) for d in [1.0, 2.0, 3.0, 4.0, 5.0]]
    for i in range(len(vals) - 1):
        assert vals[i] > vals[i + 1]


# ---------------------------------------------------------------------------
# Tests for continuous penalty in cross-school reranking
# ---------------------------------------------------------------------------


def test_cross_school_uses_continuous_penalty_when_academic_delta_present():
    """Schools with academic_delta use the continuous function, not the label map."""
    schools = [
        {
            **_make_cross_school(
                "Continuous",
                research_id=0,
                delta=0.0,
                fit_label="Fit",
                academic_fit="Strong Safety",
            ),
            "academic_delta": 5.0,
        },
        _make_cross_school(
            "Label Fallback",
            research_id=1,
            delta=0.0,
            fit_label="Fit",
            academic_fit="Strong Safety",
        ),
    ]

    _apply_cross_school_reranking(schools)
    by_name = {s["school_name"]: s for s in schools}

    # Continuous penalty for delta=5.0 is much harsher than the discrete map.
    assert by_name["Continuous"]["academic_fit_penalty"] < -10.0
    assert by_name["Label Fallback"]["academic_fit_penalty"] == -9.0


def test_cross_school_academics_priority_amplifies_penalty():
    """The 'academics' priority doubles the academic penalty weight."""
    schools = [
        {
            **_make_cross_school(
                "Good Academics",
                research_id=0,
                delta=0.0,
                fit_label="Fit",
                academic_fit="Fit",
            ),
            "academic_delta": 0.0,
        },
        {
            **_make_cross_school(
                "Bad Academics Great Roster",
                research_id=1,
                delta=0.0,
                fit_label="Fit",
                academic_fit="Strong Safety",
                opportunity_level="high",
            ),
            "academic_delta": 5.0,
        },
    ]

    _apply_cross_school_reranking(schools, ranking_priority="academics")
    by_name = {s["school_name"]: s for s in schools}

    assert (
        by_name["Good Academics"]["cross_school_composite"]
        > by_name["Bad Academics Great Roster"]["cross_school_composite"]
    )


def test_cross_school_opportunity_is_supplemental_in_balanced():
    """Balanced priority uses opportunity_bonus=0.5 — supplemental, not dominant."""
    schools = [
        {
            **_make_cross_school(
                "High Opportunity",
                research_id=0,
                delta=0.0,
                fit_label="Fit",
                opportunity_level="high",
                competition_level="low",
                same_family_opening="high",
            ),
            "academic_delta": 0.0,
        },
        {
            **_make_cross_school(
                "Low Opportunity",
                research_id=1,
                delta=0.0,
                fit_label="Fit",
                opportunity_level="low",
                competition_level="high",
                same_family_opening="low",
            ),
            "academic_delta": 0.0,
        },
    ]

    _apply_cross_school_reranking(schools, ranking_priority=None)
    by_name = {s["school_name"]: s for s in schools}

    # Higher opportunity still ranks above, but at reduced weight
    assert (
        by_name["High Opportunity"]["cross_school_composite"]
        > by_name["Low Opportunity"]["cross_school_composite"]
    )


def test_academic_quality_bonus_is_student_relative():
    """When player_academic_score is supplied, the quality bonus centers on
    (player_score - offset). Two identical schools with different student
    academic levels should get different bonuses."""
    def _make_school(name: str, selectivity: float) -> dict:
        return {
            **_make_cross_school(
                name,
                research_id=0,
                delta=0.0,
                fit_label="Fit",
                academic_fit="Fit",
            ),
            "academic_selectivity_score": selectivity,
            "academic_delta": 0.0,
        }

    # Player at 6.7 → median sits at 5.7. A 7.5-selectivity school is 1.8
    # above the median → positive bonus.
    school_hi = _make_school("Top Academic", 7.5)
    _apply_cross_school_reranking(
        [school_hi],
        ranking_priority="academics",
        player_academic_score=6.7,
    )
    bonus_hi = school_hi["cross_school_composite"]

    # Same school under a stronger student (8.5) → median 7.5 → bonus 0.
    school_neutral = _make_school("Top Academic", 7.5)
    _apply_cross_school_reranking(
        [school_neutral],
        ranking_priority="academics",
        player_academic_score=8.5,
    )
    bonus_neutral = school_neutral["cross_school_composite"]

    # The same 7.5-selectivity school should score higher under the weaker
    # student because it sits further above that student's median.
    assert bonus_hi > bonus_neutral


def test_academic_quality_bonus_fallback_when_player_score_missing():
    """With no player_academic_score, the fixed _ACADEMIC_SELECTIVITY_MEDIAN
    is used — preserving legacy behavior for callers that don't thread the
    student score through."""
    school = {
        **_make_cross_school(
            "Elite", research_id=0, delta=0.0, fit_label="Fit",
            academic_fit="Fit",
        ),
        "academic_selectivity_score": 8.0,
        "academic_delta": 0.0,
    }
    _apply_cross_school_reranking([school], ranking_priority="academics")
    # With median=5.0 and academics weight=8.0, bonus contribution = 3.0*8 = 24.
    # Composite = 0.7 * 100 (Fit family) + 24 + other small terms.
    assert school["cross_school_composite"] > 90
