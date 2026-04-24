"""Deep school insights package.

Split from the former ``backend/llm/deep_school_insights.py`` monolith.
This ``__init__`` re-exports the full public (and test-facing) surface so
existing imports like::

    from backend.llm.deep_school_insights import DeepSchoolInsightService

continue to work unchanged.
"""

from __future__ import annotations

from .evidence import (
    _empty_evidence,
    _estimate_competition,
    _estimate_openings,
    _estimate_opportunity,
    _has_meaningful_evidence,
    _player_archetype,
    _safe_int,
    _school_position_family,
    compute_evidence,
)
from .fetch import (
    fetch_and_parse_roster,
    fetch_and_parse_stats,
    gather_evidence,
    make_httpx_client,
)
from .llm_review import review_input, review_instructions, review_school
from .parsers import (
    DEFAULT_TRUSTED_DOMAINS,
    OFFICIAL_SOURCE_TYPES,
    _build_parsed_players,
    _dedupe_parsed_players,
    _looks_like_college,
    _normalize_domain,
    _normalize_name_parts,
    _parse_int,
    _parsed_player_quality,
    _parsed_roster_quality,
    _position_family_from_raw,
    _trusted_domains_for_school,
    clean_soup,
    match_players_to_stats,
    parse_roster_players,
    parse_stats_records,
)
from .ranking import (
    ACADEMIC_FIT_PENALTY_MAP,
    ACADEMIC_PRIORITY_PENALTY_MAP,
    ADJUSTMENT_POINTS,
    COMPETITION_POINTS,
    CONFIDENCE_MULTIPLIER,
    CROSS_SCHOOL_OPPORTUNITY_WEIGHT,
    CROSS_SCHOOL_Z_CLAMP,
    FIT_FAMILY_BASE,
    FIT_FAMILY_BASE_BY_PRIORITY,
    LEVEL_POINTS,
    MAX_RERANK_ADJUSTMENT,
    OPENING_POINTS,
    POSITION_DATA_POINTS,
    PRIORITY_WEIGHTS,
    RESEARCH_QUALITY_BONUS,
    ROSTER_COMPETITION_LEVEL,
    ROSTER_LABEL_CROWDED_THRESHOLD,
    ROSTER_LABEL_OPEN_THRESHOLD,
    ROSTER_OPENING_LEVEL,
    ROSTER_OPPORTUNITY_LEVEL,
    VALID_RANKING_PRIORITIES,
    _academic_penalty,
    _apply_cross_school_reranking,
    _clamp,
    _compute_relative_opportunity_metrics,
    _cross_school_sort_key,
    _review_confidence_multiplier,
    compute_ranking_adjustment,
    compute_ranking_score,
    compute_raw_opportunity_signal,
    compute_roster_label,
)
from .service import (
    DeepSchoolInsightService,
    _is_retryable,
    _research_error_message,
)
from .types import (
    HIGH_USAGE_GS_THRESHOLD,
    DeepSchoolInsight,
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


__all__ = [
    # Public API (originally exported)
    "DeepSchoolInsightService",
    "compute_raw_opportunity_signal",
    "compute_ranking_adjustment",
    "compute_ranking_score",
    "compute_roster_label",
    # Types
    "DeepSchoolInsight",
    "DeepSchoolReview",
    "GatheredEvidence",
    "MatchedPlayer",
    "OpportunityContext",
    "ParsedPlayer",
    "ParsedStatLine",
    "RecruitingContext",
    "ResearchSource",
    "RosterContext",
    "HIGH_USAGE_GS_THRESHOLD",
    # Scoring constants
    "ACADEMIC_FIT_PENALTY_MAP",
    "ACADEMIC_PRIORITY_PENALTY_MAP",
    "ADJUSTMENT_POINTS",
    "COMPETITION_POINTS",
    "CONFIDENCE_MULTIPLIER",
    "CROSS_SCHOOL_OPPORTUNITY_WEIGHT",
    "CROSS_SCHOOL_Z_CLAMP",
    "FIT_FAMILY_BASE",
    "FIT_FAMILY_BASE_BY_PRIORITY",
    "LEVEL_POINTS",
    "MAX_RERANK_ADJUSTMENT",
    "OPENING_POINTS",
    "POSITION_DATA_POINTS",
    "PRIORITY_WEIGHTS",
    "RESEARCH_QUALITY_BONUS",
    "ROSTER_COMPETITION_LEVEL",
    "ROSTER_LABEL_CROWDED_THRESHOLD",
    "ROSTER_LABEL_OPEN_THRESHOLD",
    "ROSTER_OPENING_LEVEL",
    "ROSTER_OPPORTUNITY_LEVEL",
    "VALID_RANKING_PRIORITIES",
    # Parsers
    "DEFAULT_TRUSTED_DOMAINS",
    "OFFICIAL_SOURCE_TYPES",
    "clean_soup",
    "match_players_to_stats",
    "parse_roster_players",
    "parse_stats_records",
    # Fetch
    "fetch_and_parse_roster",
    "fetch_and_parse_stats",
    "gather_evidence",
    "make_httpx_client",
    # LLM review
    "review_input",
    "review_instructions",
    "review_school",
    # Evidence
    "compute_evidence",
    # Internal helpers preserved for tests
    "_academic_penalty",
    "_apply_cross_school_reranking",
    "_build_parsed_players",
    "_clamp",
    "_compute_relative_opportunity_metrics",
    "_cross_school_sort_key",
    "_dedupe_parsed_players",
    "_empty_evidence",
    "_estimate_competition",
    "_estimate_openings",
    "_estimate_opportunity",
    "_has_meaningful_evidence",
    "_is_retryable",
    "_looks_like_college",
    "_normalize_domain",
    "_normalize_name_parts",
    "_parse_int",
    "_parsed_player_quality",
    "_parsed_roster_quality",
    "_player_archetype",
    "_position_family_from_raw",
    "_research_error_message",
    "_review_confidence_multiplier",
    "_safe_int",
    "_school_position_family",
    "_trusted_domains_for_school",
]
