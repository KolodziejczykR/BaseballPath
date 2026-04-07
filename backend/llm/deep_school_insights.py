"""
Deeper LLM-backed school research for evaluation matches.

Flow per school:
1. Fetch the official roster and stats pages with httpx.
2. Parse roster HTML into structured player records (position, class year,
   transfer status) using the existing SIDEARM scraper and roster_parser.
3. Parse stats HTML into structured stat lines (GP-GS, AVG, ERA, etc.).
4. Cross-reference players with stats by jersey number + name.
5. Compute GatheredEvidence deterministically (counts, departures, openings).
6. Pass deterministic evidence to the LLM reviewer for fit interpretation.
7. Apply a deterministic rerank adjustment from the review output.

Steps 1-5 are pure Python (no LLM).  Only step 6 uses an LLM call.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup, Comment
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from backend.evaluation.competitiveness import classify_fit
from backend.roster_scraper.roster_parser import normalize_class_year, normalize_position
from backend.roster_scraper.sidearm_scraper import SidearmRosterScraper

logger = logging.getLogger(__name__)

OFFICIAL_SOURCE_TYPES = {
    "official_roster",
    "official_stats",
    "official_news",
    "official_signing",
    "official_schedule",
    "official_bio",
    "official_conference",
    "official_ncaa",
}
DEFAULT_TRUSTED_DOMAINS = {
    "ncaa.com",
    "www.ncaa.com",
    "stats.ncaa.org",
    "perfectgame.org",
    "www.perfectgame.org",
    "prepbaseball.com",
    "www.prepbaseball.com",
    "prepbaseballreport.com",
    "www.prepbaseballreport.com",
}
CONFIDENCE_MULTIPLIER = {"high": 1.0, "medium": 0.7, "low": 0.35}
LEVEL_POINTS = {"high": 8.0, "medium": 3.0, "low": -5.0, "unknown": 0.0}
COMPETITION_POINTS = {"low": 5.0, "medium": 1.0, "high": -5.0, "unknown": 0.0}
OPENING_POINTS = {"high": 4.0, "medium": 2.0, "low": -2.0, "unknown": 0.0}
POSITION_DATA_POINTS = {"exact": 2.0, "mixed": 1.0, "family_only": 0.0, "unknown": 0.0}
ADJUSTMENT_POINTS = {"up_one": 6.0, "none": 0.0, "down_one": -6.0}
MAX_RERANK_ADJUSTMENT = 14.0

# Roster opportunity scoring for the Open / Competitive / Crowded label.
ROSTER_OPPORTUNITY_LEVEL = {"high": 3.0, "medium": 1.0, "low": -2.0, "unknown": 0.0}
ROSTER_COMPETITION_LEVEL = {"low": 2.0, "medium": 0.0, "high": -2.0, "unknown": 0.0}
ROSTER_OPENING_LEVEL = {"high": 3.0, "medium": 1.0, "low": -1.0, "unknown": 0.0}
ROSTER_LABEL_OPEN_THRESHOLD = 4.0
ROSTER_LABEL_CROWDED_THRESHOLD = -2.0

# Bonus added to ranking_adjustment when research produces meaningful evidence.
RESEARCH_QUALITY_BONUS = 1.5

# Cross-school reranking constants.
CROSS_SCHOOL_OPPORTUNITY_WEIGHT = 2.5
CROSS_SCHOOL_Z_CLAMP = 2.5
ACADEMIC_FIT_PENALTY_MAP = {"safety": 0.0, "fit": 0.0, "reach": -3.0}
FIT_FAMILY_BASE = {
    "Fit": 150.0,
    "Safety": 75.0,
    "Strong Safety": 75.0,
    "Reach": 0.0,
    "Strong Reach": 0.0,
}


class ResearchSource(BaseModel):
    label: str = ""
    url: str = ""
    source_type: str = "other"
    supports: List[str] = Field(default_factory=list)


class RosterContext(BaseModel):
    position_data_quality: Literal["exact", "mixed", "family_only", "unknown"] = "unknown"
    same_family_count: Optional[int] = None
    same_family_upperclassmen: Optional[int] = None
    same_family_underclassmen: Optional[int] = None
    same_exact_position_count: Optional[int] = None
    likely_departures_same_family: Optional[int] = None
    likely_departures_exact_position: Optional[int] = None
    returning_high_usage_same_family: Optional[int] = None
    returning_high_usage_exact_position: Optional[int] = None
    starter_opening_estimate_same_family: Literal["high", "medium", "low", "unknown"] = "unknown"
    starter_opening_estimate_exact_position: Literal["high", "medium", "low", "unknown"] = "unknown"
    notes: List[str] = Field(default_factory=list)


class RecruitingContext(BaseModel):
    incoming_same_family_recruits: Optional[int] = None
    incoming_exact_position_recruits: Optional[int] = None
    incoming_same_family_transfers: Optional[int] = None
    impact_additions_same_family: Optional[int] = None
    notes: List[str] = Field(default_factory=list)


class OpportunityContext(BaseModel):
    competition_level: Literal["high", "medium", "low", "unknown"] = "unknown"
    opportunity_level: Literal["high", "medium", "low", "unknown"] = "unknown"
    reasoning_notes: List[str] = Field(default_factory=list)


class GatheredEvidence(BaseModel):
    roster_context: RosterContext = Field(default_factory=RosterContext)
    recruiting_context: RecruitingContext = Field(default_factory=RecruitingContext)
    opportunity_context: OpportunityContext = Field(default_factory=OpportunityContext)
    sources: List[ResearchSource] = Field(default_factory=list)
    data_gaps: List[str] = Field(default_factory=list)


class DeepSchoolReview(BaseModel):
    base_athletic_fit: str = ""
    opportunity_fit: str = ""
    final_school_view: str = ""
    adjustment_from_base: Literal["none", "up_one", "down_one"] = "none"
    confidence: Literal["high", "medium", "low"] = "low"
    fit_summary: str = ""
    program_summary: str = ""
    roster_summary: str = ""
    opportunity_summary: str = ""
    trend_summary: str = ""
    reasons_for_fit: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    data_gaps: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Pre-warm Pydantic schemas eagerly.  Even though we no longer use
# asyncio.to_thread() (AsyncOpenAI handles concurrency natively), we
# still build all schemas at import time to avoid any lazy init overhead
# on the first request.
# ---------------------------------------------------------------------------
ResearchSource.model_rebuild()
RosterContext.model_rebuild()
RecruitingContext.model_rebuild()
OpportunityContext.model_rebuild()
GatheredEvidence.model_rebuild()
DeepSchoolReview.model_rebuild()
ResearchSource.model_json_schema()
RosterContext.model_json_schema()
RecruitingContext.model_json_schema()
OpportunityContext.model_json_schema()
GatheredEvidence.model_json_schema()
DeepSchoolReview.model_json_schema()


@dataclass
class DeepSchoolInsight:
    school_name: str
    evidence: GatheredEvidence
    review: DeepSchoolReview
    ranking_adjustment: float
    ranking_score: float
    research_status: str


# ---------------------------------------------------------------------------
# Intermediate structures for deterministic roster/stats parsing
# ---------------------------------------------------------------------------

@dataclass
class ParsedPlayer:
    name: str
    jersey_number: Optional[str] = None
    position_raw: Optional[str] = None
    position_normalized: Optional[str] = None
    position_family: Optional[str] = None
    class_year_raw: Optional[str] = None
    normalized_class_year: Optional[int] = None
    is_redshirt: bool = False
    high_school: Optional[str] = None
    previous_school: Optional[str] = None
    hometown: Optional[str] = None


@dataclass
class ParsedStatLine:
    jersey_number: Optional[str] = None
    player_name: str = ""
    stat_type: str = ""
    games_played: int = 0
    games_started: int = 0


@dataclass
class MatchedPlayer:
    player: ParsedPlayer
    batting_stats: Optional[ParsedStatLine] = None
    pitching_stats: Optional[ParsedStatLine] = None


HIGH_USAGE_GS_THRESHOLD = 10

_COLLEGE_KEYWORDS = re.compile(
    r"\b(university|college|community\s+college|cc|jc|juco|institute)\b",
    re.IGNORECASE,
)


def _looks_like_college(name: str) -> bool:
    return bool(_COLLEGE_KEYWORDS.search(name))


def _normalize_name_parts(name: str) -> Tuple[str, str]:
    """Return (first, last) from either 'First Last' or 'Last, First' format."""
    name = re.sub(r"\d+", "", name).strip()
    if "," in name:
        parts = name.split(",", 1)
        return parts[1].strip().lower(), parts[0].strip().lower()
    parts = name.rsplit(None, 1)
    if len(parts) == 2:
        return parts[0].strip().lower(), parts[1].strip().lower()
    return "", name.strip().lower()


def _normalize_domain(url: str) -> str:
    if not url:
        return ""
    domain = urlparse(url).netloc.strip().lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def _trusted_domains_for_school(school: Dict[str, Any]) -> List[str]:
    domains = set(DEFAULT_TRUSTED_DOMAINS)
    for key in (
        "athletics_url",
        "athletics_website",
        "roster_url",
        "school_website",
        "website",
        "school_url",
        "conference_url",
    ):
        value = school.get(key)
        if isinstance(value, str):
            domain = _normalize_domain(value)
            if domain:
                domains.add(domain)
    return sorted(domains)


def _empty_evidence(reason: str) -> GatheredEvidence:
    return GatheredEvidence(
        roster_context=RosterContext(),
        recruiting_context=RecruitingContext(),
        opportunity_context=OpportunityContext(),
        sources=[],
        data_gaps=[reason],
    )


def _has_meaningful_evidence(evidence: GatheredEvidence) -> bool:
    roster = evidence.roster_context
    recruiting = evidence.recruiting_context
    opportunity = evidence.opportunity_context

    return any(
        (
            roster.position_data_quality != "unknown",
            _safe_int(roster.same_family_count) > 0,
            _safe_int(roster.same_family_upperclassmen) > 0,
            _safe_int(roster.same_family_underclassmen) > 0,
            roster.same_exact_position_count is not None and _safe_int(roster.same_exact_position_count) >= 0,
            _safe_int(roster.likely_departures_same_family) > 0,
            _safe_int(roster.likely_departures_exact_position) > 0,
            _safe_int(roster.returning_high_usage_same_family) > 0,
            _safe_int(roster.returning_high_usage_exact_position) > 0,
            roster.starter_opening_estimate_same_family != "unknown",
            roster.starter_opening_estimate_exact_position != "unknown",
            _safe_int(recruiting.incoming_same_family_recruits) > 0,
            _safe_int(recruiting.incoming_exact_position_recruits) > 0,
            _safe_int(recruiting.incoming_same_family_transfers) > 0,
            _safe_int(recruiting.impact_additions_same_family) > 0,
            opportunity.competition_level != "unknown",
            opportunity.opportunity_level != "unknown",
        )
    )


def _school_position_family(primary_position: str) -> str:
    value = (primary_position or "").strip().upper()
    if value in {"P", "RHP", "LHP"}:
        return "P"
    if value in {"C", "CATCHER"}:
        return "C"
    if value in {"OF", "LF", "CF", "RF"}:
        return "OF"
    return "INF"


def _player_archetype(player_stats: Dict[str, Any]) -> str:
    primary_position = (player_stats.get("primary_position") or "").strip().upper()
    if primary_position in {"SS", "2B", "MI"}:
        return "middle_infield_candidate"
    if primary_position in {"3B", "1B"}:
        return "corner_infield_candidate"
    if primary_position == "CF":
        return "center_field_candidate"
    if primary_position in {"LF", "RF"}:
        return "corner_outfield_candidate"
    if primary_position in {"RHP", "LHP", "P"}:
        return "pitcher_candidate"
    if primary_position == "C":
        return "catcher_candidate"
    if primary_position == "OF":
        return "outfield_candidate"
    return "infield_candidate"


def _target_incoming_grad_year(player_stats: Dict[str, Any]) -> int:
    grad_year = player_stats.get("graduation_year")
    try:
        if grad_year is not None:
            return int(grad_year)
    except (TypeError, ValueError):
        pass
    try:
        return int(os.getenv("OPENAI_RESEARCH_INCOMING_GRAD_YEAR", "2027"))
    except (TypeError, ValueError):
        return 2027


def _review_confidence_multiplier(value: str) -> float:
    return CONFIDENCE_MULTIPLIER.get((value or "").lower(), 0.35)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _safe_int(value: Optional[int]) -> int:
    try:
        if value is None:
            return 0
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _parse_int(value: str) -> int:
    """Parse a string to int, returning 0 on failure."""
    try:
        return int(re.sub(r"[^\d]", "", value.strip()))
    except (ValueError, AttributeError):
        return 0


def compute_ranking_adjustment(evidence: GatheredEvidence, review: DeepSchoolReview) -> float:
    roster = evidence.roster_context
    recruiting = evidence.recruiting_context
    opportunity = evidence.opportunity_context

    raw = 0.0
    raw += LEVEL_POINTS.get(opportunity.opportunity_level, 0.0)
    raw += COMPETITION_POINTS.get(opportunity.competition_level, 0.0)
    raw += OPENING_POINTS.get(roster.starter_opening_estimate_same_family, 0.0)
    raw += (OPENING_POINTS.get(roster.starter_opening_estimate_exact_position, 0.0) * 0.75)
    raw += POSITION_DATA_POINTS.get(roster.position_data_quality, 0.0)
    raw += ADJUSTMENT_POINTS.get(review.adjustment_from_base, 0.0)
    raw += min(_safe_int(roster.likely_departures_same_family), 4)
    raw -= min(_safe_int(recruiting.impact_additions_same_family) * 1.5, 5.0)
    raw -= min(_safe_int(recruiting.incoming_same_family_transfers) * 1.0, 3.0)

    scaled = raw * _review_confidence_multiplier(review.confidence)
    return round(_clamp(scaled, -MAX_RERANK_ADJUSTMENT, MAX_RERANK_ADJUSTMENT), 2)


def compute_roster_label(evidence: GatheredEvidence) -> str:
    """Compute a roster opportunity label: ``open``, ``competitive``, or ``crowded``.

    The label is derived deterministically from the gathered roster/recruiting
    evidence.  Schools with no meaningful evidence return ``"unknown"``.
    """
    if not _has_meaningful_evidence(evidence):
        return "unknown"

    roster = evidence.roster_context
    recruiting = evidence.recruiting_context
    opportunity = evidence.opportunity_context

    score = 0.0
    score += ROSTER_OPPORTUNITY_LEVEL.get(opportunity.opportunity_level, 0.0)
    score += ROSTER_COMPETITION_LEVEL.get(opportunity.competition_level, 0.0)
    score += ROSTER_OPENING_LEVEL.get(roster.starter_opening_estimate_same_family, 0.0)
    score += min(_safe_int(roster.likely_departures_same_family), 3) * 1.0
    score -= min(_safe_int(recruiting.incoming_same_family_transfers), 3) * 1.0
    score -= min(_safe_int(recruiting.impact_additions_same_family), 3) * 1.5

    if score >= ROSTER_LABEL_OPEN_THRESHOLD:
        return "open"
    if score < ROSTER_LABEL_CROWDED_THRESHOLD:
        return "crowded"
    return "competitive"


def compute_ranking_score(delta: float, ranking_adjustment: float) -> float:
    """Compute a fit-centered ranking score.

    Schools closest to Fit (delta=0) score highest.  Reaches are slightly
    preferred over equivalent safeties (aspirational > fallback).  The
    ranking_adjustment from roster research can promote or demote a school.
    """
    if delta >= 0:
        fit_distance = delta * 1.0
    else:
        fit_distance = abs(delta) * 0.85
    return round(-fit_distance + ranking_adjustment, 2)


def compute_raw_opportunity_signal(school: Dict[str, Any]) -> Optional[float]:
    """Extract a deterministic roster opportunity signal from a researched school."""
    if school.get("research_status") not in ("completed", "partial"):
        return None

    packet = school.get("research_packet")
    if not isinstance(packet, dict) or not packet:
        return None

    roster = packet.get("roster_context") or {}
    recruiting = packet.get("recruiting_context") or {}
    opportunity = packet.get("opportunity_context") or {}

    signal = 0.0
    signal += LEVEL_POINTS.get(opportunity.get("opportunity_level", "unknown"), 0.0)
    signal += COMPETITION_POINTS.get(opportunity.get("competition_level", "unknown"), 0.0)
    signal += OPENING_POINTS.get(roster.get("starter_opening_estimate_same_family", "unknown"), 0.0)
    signal += OPENING_POINTS.get(roster.get("starter_opening_estimate_exact_position", "unknown"), 0.0) * 0.75
    signal += min(_safe_int(roster.get("likely_departures_same_family")), 4)
    signal -= min(_safe_int(recruiting.get("impact_additions_same_family")) * 1.5, 5.0)
    signal -= min(_safe_int(recruiting.get("incoming_same_family_transfers")) * 1.0, 3.0)
    return round(signal, 2)


def _compute_relative_opportunity_metrics(
    schools: Sequence[Dict[str, Any]],
) -> Dict[int, Dict[str, float]]:
    """Normalize researched-school opportunity signals across the pool."""
    raw_by_id: Dict[int, float] = {}

    for school in schools:
        research_id = school.get("_research_id")
        if research_id is None:
            continue
        raw_signal = compute_raw_opportunity_signal(school)
        if raw_signal is None:
            continue
        raw_by_id[int(research_id)] = float(raw_signal)

    if len(raw_by_id) < 2:
        return {}

    values = list(raw_by_id.values())
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    std_dev = max(math.sqrt(variance), 1.0)

    metrics: Dict[int, Dict[str, float]] = {}
    for research_id, raw_signal in raw_by_id.items():
        z_score = _clamp((raw_signal - mean) / std_dev, -CROSS_SCHOOL_Z_CLAMP, CROSS_SCHOOL_Z_CLAMP)
        metrics[research_id] = {
            "raw_opportunity_signal": round(raw_signal, 2),
            "relative_opportunity_zscore": round(z_score, 4),
            "relative_opportunity_bonus": round(z_score * CROSS_SCHOOL_OPPORTUNITY_WEIGHT, 2),
        }

    return metrics


def _cross_school_sort_key(school: Dict[str, Any]) -> Tuple[float, float, float]:
    return (
        float(school.get("cross_school_composite") or 0.0),
        float(school.get("ranking_score") or 0.0),
        float(school.get("delta") or 0.0),
    )


def _apply_cross_school_reranking(schools: Sequence[Dict[str, Any]]) -> None:
    """Attach family-guarded composite scores and relative opportunity metrics."""
    metrics_by_id = _compute_relative_opportunity_metrics(schools)

    for school in schools:
        school["raw_opportunity_signal"] = compute_raw_opportunity_signal(school)
        school["relative_opportunity_zscore"] = None
        school["relative_opportunity_bonus"] = 0.0
        school["academic_fit_penalty"] = ACADEMIC_FIT_PENALTY_MAP.get(
            str(school.get("academic_fit") or "").strip().lower(),
            0.0,
        )

        research_id = school.get("_research_id")
        if research_id is not None:
            metrics = metrics_by_id.get(int(research_id))
            if metrics is not None:
                school.update(metrics)

        fit_label = school.get("fit_label")
        if fit_label not in FIT_FAMILY_BASE:
            fit_label = classify_fit(float(school.get("delta") or 0.0))
            school["fit_label"] = fit_label

        composite = (
            FIT_FAMILY_BASE[fit_label]
            + float(school.get("ranking_score") or 0.0)
            + float(school.get("relative_opportunity_bonus") or 0.0)
            + float(school.get("academic_fit_penalty") or 0.0)
        )
        school["cross_school_composite"] = round(composite, 2)


class DeepSchoolInsightService:
    def __init__(
        self,
        client: Optional[AsyncOpenAI] = None,
        initial_batch_size: int = 1,
        batch_size: int = 1,
        max_schools: Optional[int] = None,
        llm_timeout_s: float = 90.0,
    ):
        api_key = os.getenv("OPENAI_API_KEY")
        self.enabled = bool(api_key or client)
        self.client = client or (AsyncOpenAI(api_key=api_key, max_retries=0) if api_key else None)
        self.review_model = os.getenv("OPENAI_REVIEW_MODEL", "gpt-5.4-nano")
        self.has_responses_parse = bool(
            self.client is not None
            and getattr(self.client, "responses", None) is not None
            and hasattr(self.client.responses, "parse")
        )
        self.initial_batch_size = max(
            1, int(os.getenv("OPENAI_RESEARCH_INITIAL_BATCH_SIZE", str(initial_batch_size)))
        )
        self.batch_size = max(
            1, int(os.getenv("OPENAI_RESEARCH_BATCH_SIZE", str(batch_size)))
        )
        max_schools_env = os.getenv("OPENAI_RESEARCH_MAX_SCHOOLS")
        self.max_schools = (
            max(1, int(max_schools_env))
            if max_schools_env
            else (max(1, int(max_schools)) if max_schools is not None else None)
        )
        self.llm_timeout_s = float(os.getenv("OPENAI_RESEARCH_TIMEOUT_S", str(llm_timeout_s)))

    async def _responses_parse(
        self,
        *,
        model: str,
        input_text: str,
        instructions: str,
        text_format: Any,
        max_output_tokens: int,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Any:
        request_kwargs: Dict[str, Any] = {
            "model": model,
            "input": input_text,
            "instructions": instructions,
            "text_format": text_format,
            "temperature": 0,
            "max_output_tokens": max_output_tokens,
        }
        if tools is not None:
            request_kwargs["tools"] = tools

        return await asyncio.wait_for(
            self.client.responses.parse(**request_kwargs),
            timeout=self.llm_timeout_s,
        )

    async def enrich_and_rerank(
        self,
        schools: List[Dict[str, Any]],
        player_stats: Dict[str, Any],
        baseball_assessment: Dict[str, Any],
        academic_score: Dict[str, Any],
        final_limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        if not self.enabled or self.client is None or not schools:
            return schools

        schools_copy = [dict(s) for s in schools]
        research_limit = len(schools_copy)
        # Finalized runs should research the entire consideration pool before
        # trimming back to the user-visible limit. Otherwise a school can make
        # the final 15 without ever receiving roster research.
        if final_limit is None and self.max_schools is not None:
            research_limit = min(research_limit, self.max_schools)

        for idx, school in enumerate(schools_copy):
            base_score = float(school.get("delta") or 0.0)
            school["ranking_score"] = compute_ranking_score(base_score, 0.0)
            school["ranking_adjustment"] = 0.0
            school["research_status"] = "queued" if idx < research_limit else "not_requested"
            school["_research_id"] = idx
            school["_research_eligible"] = idx < research_limit

        researched_ids: set[int] = set()
        batch_size = self.initial_batch_size

        while True:
            schools_copy.sort(
                key=lambda school: (
                    float(school.get("ranking_score") or 0.0),
                    float(school.get("delta") or 0.0),
                ),
                reverse=True,
            )
            next_batch = [
                school
                for school in schools_copy
                if school.get("_research_eligible") and school.get("_research_id") not in researched_ids
            ][:batch_size]
            if not next_batch:
                break

            for school in next_batch:
                school["research_status"] = "attempted"

            tasks = [
                self._enrich_single_school(
                    school=school,
                    player_stats=player_stats,
                    baseball_assessment=baseball_assessment,
                    academic_score=academic_score,
                )
                for school in next_batch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for school, result in zip(next_batch, results):
                researched_ids.add(int(school["_research_id"]))
                if isinstance(result, DeepSchoolInsight):
                    self._apply_insight(school, result)
                    continue
                if isinstance(result, Exception):
                    logger.warning(
                        "Deep school insight generation failed for %s: %s",
                        school.get("school_name"),
                        result,
                    )
                school["research_status"] = "failed"

            batch_size = self.batch_size

        _apply_cross_school_reranking(schools_copy)
        schools_copy.sort(
            key=_cross_school_sort_key,
            reverse=True,
        )

        # When a final_limit is set, select the top N schools from the
        # broader research pool.  This is the research-first selection step
        # where roster evidence directly influences which schools make the
        # final list.  Category caps prevent extreme labels from dominating.
        if final_limit is not None and len(schools_copy) > final_limit:
            MAX_STRONG_SAFETY = 2
            MAX_STRONG_REACH = 2

            strong_safeties = [s for s in schools_copy if s.get("fit_label") == "Strong Safety"]
            strong_reaches = [s for s in schools_copy if s.get("fit_label") == "Strong Reach"]
            rest = [s for s in schools_copy if s.get("fit_label") not in ("Strong Safety", "Strong Reach")]

            for group in (strong_safeties, strong_reaches, rest):
                group.sort(key=_cross_school_sort_key, reverse=True)

            selected = list(rest)
            selected.extend(strong_safeties[:MAX_STRONG_SAFETY])
            selected.extend(strong_reaches[:MAX_STRONG_REACH])
            selected.sort(key=_cross_school_sort_key, reverse=True)
            schools_copy = selected[:final_limit]

        for idx, school in enumerate(schools_copy, start=1):
            school.pop("_research_id", None)
            school.pop("_research_eligible", None)
            school["rank"] = idx

        status_counts: Dict[str, int] = {}
        for school in schools_copy:
            st = school.get("research_status", "unknown")
            status_counts[st] = status_counts.get(st, 0) + 1
        logger.info(
            "Deep school research complete: %d researched, %d final; status breakdown: %s",
            len(researched_ids),
            len(schools_copy),
            status_counts,
        )
        return schools_copy

    def _apply_insight(self, school: Dict[str, Any], insight: DeepSchoolInsight) -> None:
        school["research_status"] = insight.research_status
        school["ranking_adjustment"] = insight.ranking_adjustment
        school["ranking_score"] = insight.ranking_score
        school["research_confidence"] = insight.review.confidence
        school["roster_label"] = compute_roster_label(insight.evidence)
        school["opportunity_fit"] = insight.review.opportunity_fit
        school["overall_school_view"] = insight.review.final_school_view
        school["review_adjustment_from_base"] = insight.review.adjustment_from_base
        school["roster_summary"] = insight.review.roster_summary
        school["opportunity_summary"] = insight.review.opportunity_summary
        school["trend_summary"] = insight.review.trend_summary
        school["research_fit_summary"] = insight.review.fit_summary
        # Propagate deep review summaries as the primary fit_summary / school_description
        # so the UI shows research-backed content instead of the fast inline summary.
        if insight.review.fit_summary:
            school["fit_summary"] = insight.review.fit_summary
        if insight.review.program_summary:
            school["school_description"] = insight.review.program_summary
        school["program_summary"] = insight.review.program_summary
        school["research_reasons"] = insight.review.reasons_for_fit
        school["research_risks"] = insight.review.risks
        school["research_data_gaps"] = sorted(
            set(insight.review.data_gaps + insight.evidence.data_gaps)
        )
        school["research_sources"] = [
            source.model_dump() for source in insight.evidence.sources
        ]
        school["research_packet"] = insight.evidence.model_dump()

    async def _enrich_single_school(
        self,
        school: Dict[str, Any],
        player_stats: Dict[str, Any],
        baseball_assessment: Dict[str, Any],
        academic_score: Dict[str, Any],
    ) -> Optional[DeepSchoolInsight]:
        if self.client is None:
            return None
        if not self.has_responses_parse:
            return DeepSchoolInsight(
                school_name=school.get("school_name", ""),
                evidence=_empty_evidence(
                    "Deep roster research is unavailable because the running OpenAI SDK does not support responses.parse."
                ),
                review=DeepSchoolReview(
                    base_athletic_fit=school.get("fit_label") or "",
                    opportunity_fit="",
                    final_school_view=school.get("fit_label") or "",
                    adjustment_from_base="none",
                    confidence="low",
                    fit_summary="",
                    program_summary="",
                    roster_summary="Deep roster research is unavailable in the current backend environment.",
                    opportunity_summary="Opportunity was left unchanged because roster research could not run.",
                    trend_summary="",
                    reasons_for_fit=[],
                    risks=[],
                    data_gaps=[
                        "Deep roster research is unavailable because the running OpenAI SDK does not support responses.parse."
                    ],
                ),
                ranking_adjustment=0.0,
                ranking_score=compute_ranking_score(float(school.get("delta") or 0.0), 0.0),
                research_status="unavailable",
            )

        trusted_domains = _trusted_domains_for_school(school)
        evidence = await self._gather_evidence(school, player_stats, trusted_domains)
        if not _has_meaningful_evidence(evidence):
            return DeepSchoolInsight(
                school_name=school.get("school_name", ""),
                evidence=evidence,
                review=DeepSchoolReview(
                    base_athletic_fit=school.get("fit_label") or "",
                    opportunity_fit="",
                    final_school_view=school.get("fit_label") or "",
                    adjustment_from_base="none",
                    confidence="low",
                    fit_summary="",
                    program_summary="",
                    roster_summary="Official roster context could not be verified from source-backed results.",
                    opportunity_summary="Opportunity was left unchanged because verified roster evidence was not available.",
                    trend_summary="",
                    reasons_for_fit=[],
                    risks=[],
                    data_gaps=evidence.data_gaps,
                ),
                ranking_adjustment=0.0,
                ranking_score=compute_ranking_score(float(school.get("delta") or 0.0), 0.0),
                research_status="insufficient_evidence",
            )

        review = await self._review_school(school, player_stats, baseball_assessment, academic_score, evidence)
        if review is None:
            # Reviewer failed but evidence is valid — use a conservative fallback
            # that still captures opportunity/competition/roster-opening signals
            # at low confidence (0.35x multiplier).
            review = DeepSchoolReview(
                base_athletic_fit=school.get("fit_label") or "",
                opportunity_fit="",
                final_school_view=school.get("fit_label") or "",
                adjustment_from_base="none",
                confidence="low",
                fit_summary="",
                program_summary="",
                roster_summary="Roster evidence was gathered but the detailed review could not be completed.",
                opportunity_summary="",
                trend_summary="",
                reasons_for_fit=[],
                risks=[],
                data_gaps=evidence.data_gaps + ["Detailed review could not be completed."],
            )
            ranking_adjustment = compute_ranking_adjustment(evidence, review)
            if _has_meaningful_evidence(evidence):
                ranking_adjustment = round(min(ranking_adjustment + RESEARCH_QUALITY_BONUS * 0.5, MAX_RERANK_ADJUSTMENT), 2)
            base_score = float(school.get("delta") or 0.0)
            return DeepSchoolInsight(
                school_name=school.get("school_name", ""),
                evidence=evidence,
                review=review,
                ranking_adjustment=ranking_adjustment,
                ranking_score=compute_ranking_score(base_score, ranking_adjustment),
                research_status="partial",
            )

        ranking_adjustment = compute_ranking_adjustment(evidence, review)
        if _has_meaningful_evidence(evidence):
            ranking_adjustment = round(min(ranking_adjustment + RESEARCH_QUALITY_BONUS, MAX_RERANK_ADJUSTMENT), 2)
        base_score = float(school.get("delta") or 0.0)
        return DeepSchoolInsight(
            school_name=school.get("school_name", ""),
            evidence=evidence,
            review=review,
            ranking_adjustment=ranking_adjustment,
            ranking_score=compute_ranking_score(base_score, ranking_adjustment),
            research_status="completed",
        )

    def _httpx_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(20.0, connect=10.0),
            follow_redirects=True,
            verify=False,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            },
        )

    # ------------------------------------------------------------------
    # Deterministic roster parsing
    # ------------------------------------------------------------------

    def _parse_roster_players(self, soup: BeautifulSoup) -> List[ParsedPlayer]:
        """Parse roster HTML into structured player records using the best available layout."""
        scraper = SidearmRosterScraper.__new__(SidearmRosterScraper)
        candidates: List[List[ParsedPlayer]] = []
        for parse_fn in (
            scraper._parse_card_layout,
            scraper._parse_table_layout,
            scraper._parse_generic_table,
        ):
            raw_players = parse_fn(soup)
            if not raw_players:
                continue
            parsed_players = self._build_parsed_players(raw_players)
            deduped = self._dedupe_parsed_players(parsed_players)
            if deduped:
                candidates.append(deduped)

        if not candidates:
            return []

        return max(candidates, key=lambda players: (self._parsed_roster_quality(players), len(players)))

    def _build_parsed_players(self, raw_players: Sequence[Dict[str, Any]]) -> List[ParsedPlayer]:
        parsed: List[ParsedPlayer] = []
        for raw in raw_players:
            name = raw.get("name", "").strip()
            if not name:
                continue

            pos_raw = raw.get("position")
            pos_normalized = normalize_position(pos_raw) if pos_raw else None
            pos_family = self._position_family_from_raw(pos_raw) if pos_raw else None

            year_raw = raw.get("class_year")
            year_int, is_redshirt = normalize_class_year(year_raw) if year_raw else (None, False)

            previous_school = raw.get("high_school") or raw.get("previous_school")

            parsed.append(ParsedPlayer(
                name=name,
                jersey_number=raw.get("jersey_number"),
                position_raw=pos_raw,
                position_normalized=pos_normalized,
                position_family=pos_family,
                class_year_raw=year_raw,
                normalized_class_year=year_int,
                is_redshirt=is_redshirt,
                high_school=previous_school if previous_school and not _looks_like_college(previous_school) else None,
                previous_school=previous_school if previous_school and _looks_like_college(previous_school) else None,
                hometown=raw.get("hometown"),
            ))
        return parsed

    @staticmethod
    def _dedupe_parsed_players(players: Sequence[ParsedPlayer]) -> List[ParsedPlayer]:
        deduped: Dict[Tuple[str, str], ParsedPlayer] = {}
        for player in players:
            key = (
                " ".join((player.name or "").strip().lower().split()),
                (player.jersey_number or "").strip().lower(),
            )
            existing = deduped.get(key)
            if existing is None or DeepSchoolInsightService._parsed_player_quality(player) > DeepSchoolInsightService._parsed_player_quality(existing):
                deduped[key] = player
        return list(deduped.values())

    @staticmethod
    def _parsed_player_quality(player: ParsedPlayer) -> int:
        score = 0
        if player.position_raw:
            score += 2
        if player.position_family:
            score += 2
        if player.position_normalized:
            score += 2
        if player.class_year_raw:
            score += 1
        if player.normalized_class_year is not None:
            score += 2
        if player.previous_school:
            score += 1
        if player.hometown:
            score += 1
        return score

    @classmethod
    def _parsed_roster_quality(cls, players: Sequence[ParsedPlayer]) -> int:
        return sum(cls._parsed_player_quality(player) for player in players)

    @staticmethod
    def _position_family_from_raw(pos_raw: Optional[str]) -> Optional[str]:
        """Map a raw position string to its family: P, C, OF, or INF."""
        if not pos_raw:
            return None
        cleaned = pos_raw.strip().lower().replace(".", "")
        if "/" in cleaned:
            cleaned = cleaned.split("/")[0].strip()
        if cleaned in {"p", "rhp", "lhp", "rp", "sp", "pitcher", "closer", "cl"}:
            return "P"
        if cleaned in {"c", "catcher"}:
            return "C"
        if cleaned in {"of", "lf", "cf", "rf", "outfield", "outfielder",
                        "left field", "left fielder", "center field",
                        "center fielder", "right field", "right fielder"}:
            return "OF"
        # Everything else is INF (including ambiguous IF/INF)
        return "INF"

    # ------------------------------------------------------------------
    # Deterministic stats parsing
    # ------------------------------------------------------------------

    def _parse_stats_records(self, soup: BeautifulSoup) -> List[ParsedStatLine]:
        """Parse batting and pitching stats tables into structured records."""
        records: List[ParsedStatLine] = []

        for table in soup.find_all("table"):
            headers_raw = [th.get_text(strip=True) for th in table.find_all("th")[:30]]
            headers_upper = [h.upper() for h in headers_raw]
            rows = table.find_all("tr")
            if len(rows) < 3:
                continue

            h_set = set(headers_upper)
            is_batting = bool(
                {"AVG", "AB"} & h_set
                and not {"ERA", "IP", "W-L", "APP", "APP-GS", "SV"} & h_set
            )
            is_pitching = bool(
                {"ERA", "IP", "W-L", "APP", "APP-GS", "WHIP", "SV"} & h_set
            )
            if not is_batting and not is_pitching:
                continue

            stat_type = "batting" if is_batting else "pitching"

            # Find column indices for key fields
            name_idx = None
            number_idx = None
            gp_idx = None
            gs_idx = None
            for i, h in enumerate(headers_upper):
                if h in {"PLAYER", "NAME"} or (h == "" and i <= 1):
                    name_idx = i
                elif h in {"#", "NO", "NO."}:
                    number_idx = i
                elif h == "GP" or h == "G":
                    gp_idx = i
                elif h == "GS":
                    gs_idx = i
                elif h == "GP-GS" or h == "APP-GS":
                    gp_idx = i  # combined column, parse below

            # If no explicit name column, try first non-number column
            if name_idx is None:
                for i, h in enumerate(headers_upper):
                    if h not in {"#", "NO", "NO."} and i <= 2:
                        name_idx = i
                        break

            body_rows = table.select("tbody tr") or rows[1:]
            for row in body_rows:
                cell_tags = row.find_all(["td", "th"])
                cells = [td.get_text(" ", strip=True) for td in cell_tags]
                if len(cells) < 3:
                    continue

                player_name = ""
                if name_idx is not None and name_idx < len(cells):
                    name_link = cell_tags[name_idx].select_one("a")
                    player_name = (
                        name_link.get_text(" ", strip=True) if name_link else cells[name_idx]
                    )
                # Skip totals/team rows
                if player_name.upper() in {"TOTALS", "TEAM", "OPPONENT", "OPP", "TOTAL", ""}:
                    continue

                jersey = cells[number_idx] if number_idx is not None and number_idx < len(cells) else None

                gp = 0
                gs = 0
                if gp_idx is not None and gp_idx < len(cells):
                    gp_val = cells[gp_idx]
                    if "-" in gp_val:
                        # GP-GS combined format like "30-25"
                        parts = gp_val.split("-")
                        gp = _parse_int(parts[0])
                        gs = _parse_int(parts[1]) if len(parts) > 1 else 0
                    else:
                        gp = _parse_int(gp_val)
                if gs_idx is not None and gs_idx < len(cells):
                    gs = _parse_int(cells[gs_idx])

                records.append(ParsedStatLine(
                    jersey_number=jersey,
                    player_name=player_name,
                    stat_type=stat_type,
                    games_played=gp,
                    games_started=gs,
                ))

        return records

    # ------------------------------------------------------------------
    # Player-stats matching
    # ------------------------------------------------------------------

    def _match_players_to_stats(
        self,
        players: List[ParsedPlayer],
        stats: List[ParsedStatLine],
    ) -> List[MatchedPlayer]:
        """Cross-reference roster players with stat lines by jersey + last name."""
        batting = [s for s in stats if s.stat_type == "batting"]
        pitching = [s for s in stats if s.stat_type == "pitching"]

        def _find_match(player: ParsedPlayer, stat_lines: List[ParsedStatLine]) -> Optional[ParsedStatLine]:
            p_first, p_last = _normalize_name_parts(player.name)
            for stat in stat_lines:
                s_first, s_last = _normalize_name_parts(stat.player_name)
                # Match by jersey number + last name, or full name match
                if player.jersey_number and stat.jersey_number:
                    if player.jersey_number == stat.jersey_number and p_last == s_last:
                        return stat
                # Fallback: last name + first initial match
                if p_last == s_last and p_first and s_first and p_first[0] == s_first[0]:
                    return stat
            return None

        matched: List[MatchedPlayer] = []
        for player in players:
            bat = _find_match(player, batting)
            pitch = _find_match(player, pitching)
            matched.append(MatchedPlayer(player=player, batting_stats=bat, pitching_stats=pitch))
        return matched

    # ------------------------------------------------------------------
    # Deterministic evidence computation
    # ------------------------------------------------------------------

    def _compute_evidence(
        self,
        matched_players: List[MatchedPlayer],
        player_stats: Dict[str, Any],
        roster_url: str,
        stats_available: bool,
    ) -> GatheredEvidence:
        """Build GatheredEvidence deterministically from parsed roster/stats data."""
        target_family = _school_position_family(player_stats.get("primary_position", ""))
        target_position = normalize_position(player_stats.get("primary_position", ""))

        # Filter players by position family
        same_family = [m for m in matched_players if m.player.position_family == target_family]
        same_exact = [m for m in matched_players if m.player.position_normalized == target_position] if target_position else []

        # Count by class year
        upperclassmen = sum(1 for m in same_family if (m.player.normalized_class_year or 0) >= 3)
        underclassmen = sum(1 for m in same_family if (m.player.normalized_class_year or 0) in (1, 2))

        # Departures: seniors (4) and grad students (5) are likely leaving
        departures_family = sum(
            1 for m in same_family
            if (m.player.normalized_class_year or 0) >= 4
        )
        departures_exact = sum(
            1 for m in same_exact
            if (m.player.normalized_class_year or 0) >= 4
        ) if same_exact else None

        # Transfers into the program (previous_school is a college)
        transfers_family = sum(
            1 for m in same_family
            if m.player.previous_school is not None
        )

        # Position data quality should reflect the roster parse as a whole, not
        # only the matched family subset. Otherwise a valid roster with no
        # target-family players is indistinguishable from a roster where
        # positions failed to parse entirely.
        players_with_positions = [
            m for m in matched_players if m.player.position_family is not None
        ]
        has_exact = any(m.player.position_normalized is not None for m in players_with_positions)
        has_ambiguous = any(
            m.player.position_normalized is None and m.player.position_family is not None
            for m in players_with_positions
        )
        if has_exact and not has_ambiguous:
            pos_quality = "exact"
        elif has_exact and has_ambiguous:
            pos_quality = "mixed"
        elif has_ambiguous:
            pos_quality = "family_only"
        else:
            pos_quality = "unknown"

        # High-usage returning players (based on stats GP-GS)
        returning_high_usage_family = 0
        returning_high_usage_exact = 0
        if stats_available:
            for m in same_family:
                if (m.player.normalized_class_year or 0) >= 4:
                    continue  # departing
                stat = m.batting_stats or m.pitching_stats
                if stat and stat.games_started >= HIGH_USAGE_GS_THRESHOLD:
                    returning_high_usage_family += 1
                    if target_position and m.player.position_normalized == target_position:
                        returning_high_usage_exact += 1

        # Estimate starter openings
        opener_family = self._estimate_openings(
            departures=departures_family,
            total=len(same_family),
            returning_high_usage=returning_high_usage_family if stats_available else None,
        )
        opener_exact = self._estimate_openings(
            departures=departures_exact or 0,
            total=len(same_exact),
            returning_high_usage=returning_high_usage_exact if stats_available else None,
        ) if same_exact else "unknown"

        # Opportunity and competition levels
        opportunity = self._estimate_opportunity(
            departures=departures_family,
            total=len(same_family),
            returning_starters=returning_high_usage_family if stats_available else None,
        )
        competition = self._estimate_competition(
            total=len(same_family),
            returning_starters=returning_high_usage_family if stats_available else None,
            underclassmen=underclassmen,
        )

        # Notes
        notes: List[str] = []
        if not stats_available:
            notes.append("Stats page was not available; estimates based on roster data only.")
        if pos_quality == "family_only":
            notes.append("Position listings use broad categories (IF/OF/P); exact positions unknown.")
        if pos_quality != "unknown" and not same_family:
            notes.append(f"No listed players matched the {target_family} position family on the roster.")

        # Sources
        sources = [
            ResearchSource(
                label="Official roster page",
                url=roster_url,
                source_type="official_roster",
                supports=[
                    "same_family_count", "same_exact_position_count",
                    "likely_departures_same_family", "position_data_quality",
                    "same_family_upperclassmen", "same_family_underclassmen",
                ],
            )
        ]
        if stats_available:
            stats_url = roster_url.replace("/roster", "/stats") if "/roster" in roster_url else ""
            if stats_url:
                sources.append(ResearchSource(
                    label="Official stats page",
                    url=stats_url,
                    source_type="official_stats",
                    supports=[
                        "returning_high_usage_same_family",
                        "returning_high_usage_exact_position",
                        "starter_opening_estimate_same_family",
                    ],
                ))

        data_gaps: List[str] = []
        if not stats_available:
            data_gaps.append("Team statistics unavailable — starter usage estimates less precise.")

        return GatheredEvidence(
            roster_context=RosterContext(
                position_data_quality=pos_quality,
                same_family_count=len(same_family),
                same_family_upperclassmen=upperclassmen,
                same_family_underclassmen=underclassmen,
                same_exact_position_count=len(same_exact) if same_exact else None,
                likely_departures_same_family=departures_family,
                likely_departures_exact_position=departures_exact,
                returning_high_usage_same_family=returning_high_usage_family if stats_available else None,
                returning_high_usage_exact_position=returning_high_usage_exact if stats_available else None,
                starter_opening_estimate_same_family=opener_family,
                starter_opening_estimate_exact_position=opener_exact,
                notes=notes,
            ),
            recruiting_context=RecruitingContext(
                incoming_same_family_transfers=transfers_family,
            ),
            opportunity_context=OpportunityContext(
                competition_level=competition,
                opportunity_level=opportunity,
            ),
            sources=sources,
            data_gaps=data_gaps,
        )

    @staticmethod
    def _estimate_openings(departures: int, total: int, returning_high_usage: Optional[int]) -> str:
        if total == 0:
            return "unknown"
        departure_ratio = departures / total
        if returning_high_usage is not None:
            if departures >= 3 and returning_high_usage <= 2:
                return "high"
            if departures >= 2 and returning_high_usage <= 3:
                return "medium"
            if departures <= 1 and returning_high_usage >= 4:
                return "low"
        # Fallback without stats
        if departure_ratio >= 0.3:
            return "high"
        if departure_ratio >= 0.15:
            return "medium"
        return "low"

    @staticmethod
    def _estimate_opportunity(departures: int, total: int, returning_starters: Optional[int]) -> str:
        if total == 0:
            return "unknown"
        if departures >= 3:
            return "high"
        if returning_starters is not None and returning_starters <= 1 and departures >= 2:
            return "high"
        if departures >= 2:
            return "medium"
        return "low"

    @staticmethod
    def _estimate_competition(total: int, returning_starters: Optional[int], underclassmen: int) -> str:
        if total == 0:
            return "unknown"
        if returning_starters is not None:
            if returning_starters >= 5:
                return "high"
            if returning_starters >= 3:
                return "medium"
            return "low"
        # Without stats, use roster depth
        if total >= 8 and underclassmen >= 4:
            return "high"
        if total >= 5:
            return "medium"
        return "low"

    @staticmethod
    def _clean_soup(html: str) -> BeautifulSoup:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all(["script", "style", "nav", "footer", "header", "iframe"]):
            tag.decompose()
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            comment.extract()
        return soup

    async def _fetch_and_parse_roster(
        self, school: Dict[str, Any],
    ) -> Tuple[List[ParsedPlayer], Optional[str]]:
        """Fetch roster page and parse into structured player records.

        Returns (players, roster_url).  On failure returns ([], roster_url).
        Raises ValueError if roster_url is missing.
        """
        roster_url = school.get("roster_url")
        if not roster_url:
            raise ValueError(
                f"Missing roster_url for {school.get('school_name', 'Unknown')}. "
                "Every school must have a full roster URL in the database."
            )

        school_name = school.get("display_school_name") or school.get("school_name") or "Unknown"
        try:
            async with self._httpx_client() as client:
                resp = await client.get(roster_url)
                resp.raise_for_status()
        except Exception as exc:
            logger.info("Roster page fetch failed for %s (%s): %s", school_name, roster_url, exc)
            return [], roster_url

        soup = self._clean_soup(resp.text)
        players = self._parse_roster_players(soup)
        logger.info(
            "Parsed %d players from roster for %s (%s)", len(players), school_name, roster_url,
        )
        return players, roster_url

    async def _fetch_and_parse_stats(
        self, school: Dict[str, Any],
    ) -> List[ParsedStatLine]:
        """Fetch stats page and parse into structured stat records.

        Derives stats URL by replacing /roster with /stats.
        Returns empty list if stats are unavailable.
        Retries once after a delay for JS-heavy sites.
        """
        roster_url = school.get("roster_url", "")
        if not roster_url or "/roster" not in roster_url.lower():
            return []

        stats_url = roster_url.replace("/roster", "/stats")
        school_name = school.get("display_school_name") or school.get("school_name") or "Unknown"

        async with self._httpx_client() as client:
            for attempt in range(2):
                try:
                    resp = await client.get(stats_url)
                    if resp.status_code == 404:
                        logger.info("Stats page 404 for %s, skipping", school_name)
                        return []
                    resp.raise_for_status()
                except Exception as exc:
                    if attempt == 0:
                        logger.info(
                            "Stats fetch attempt 1 failed for %s (%s): %s — retrying in 10s",
                            school_name, stats_url, exc,
                        )
                        await asyncio.sleep(10.0)
                        continue
                    logger.info("Stats fetch failed for %s after retry: %s", school_name, exc)
                    return []

                soup = self._clean_soup(resp.text)
                records = self._parse_stats_records(soup)

                if records:
                    logger.info(
                        "Parsed %d stat lines for %s from %s",
                        len(records), school_name, stats_url,
                    )
                    return records

                if attempt == 0:
                    logger.info(
                        "Stats page for %s had no stat tables on attempt 1 — retrying in 10s",
                        school_name,
                    )
                    await asyncio.sleep(10.0)
                    continue

                logger.info("Stats page for %s had no usable stat tables after retry", school_name)
                return []

        return []

    async def _gather_evidence(
        self,
        school: Dict[str, Any],
        player_stats: Dict[str, Any],
        trusted_domains: Sequence[str],
    ) -> GatheredEvidence:
        """Gather evidence deterministically: fetch, parse, match, compute."""
        school_name = school.get("display_school_name") or school.get("school_name") or "Unknown School"

        # Fetch roster and stats concurrently
        roster_coro = self._fetch_and_parse_roster(school)
        stats_coro = self._fetch_and_parse_stats(school)
        (players, roster_url), stats = await asyncio.gather(roster_coro, stats_coro)

        if not players:
            logger.info("No players parsed for %s — returning empty evidence", school_name)
            return _empty_evidence(f"Could not parse roster for {school_name}.")

        # Match players to stats
        matched = self._match_players_to_stats(players, stats)

        # Compute evidence deterministically
        evidence = self._compute_evidence(
            matched_players=matched,
            player_stats=player_stats,
            roster_url=roster_url or "",
            stats_available=bool(stats),
        )

        logger.info(
            "Computed evidence for %s: %d players, %d same-family, %d departures, stats=%s",
            school_name,
            len(players),
            evidence.roster_context.same_family_count or 0,
            evidence.roster_context.likely_departures_same_family or 0,
            "yes" if stats else "no",
        )
        return evidence

    async def _review_school(
        self,
        school: Dict[str, Any],
        player_stats: Dict[str, Any],
        baseball_assessment: Dict[str, Any],
        academic_score: Dict[str, Any],
        evidence: GatheredEvidence,
    ) -> Optional[DeepSchoolReview]:
        school_name = school.get("display_school_name") or school.get("school_name") or "Unknown School"
        try:
            response = await self._responses_parse(
                model=self.review_model,
                input_text=self._review_input(
                    school,
                    player_stats,
                    baseball_assessment,
                    academic_score,
                    evidence,
                ),
                instructions=self._review_instructions(),
                text_format=DeepSchoolReview,
                max_output_tokens=2500,
            )
        except Exception as exc:
            logger.warning("Deep school reviewer failed for %s: %s", school_name, exc)
            return None
        return getattr(response, "output_parsed", None)

    def _review_instructions(self) -> str:
        return (
            "You are a college baseball fit reviewer.\n"
            "You will receive a JSON packet containing:\n"
            "- Pre-computed roster evidence (position counts, departures, openings, transfers)\n"
            "- The player's athletic profile and metrics\n"
            "- The base athletic fit assessment\n\n"
            "Your job is to INTERPRET the evidence and write concise summaries.\n"
            "Use the deterministic athletic metrics as the base layer and use the roster evidence "
            "only to refine the school-level interpretation.\n"
            "Never invent roster facts — all counts and estimates are already computed for you.\n"
            "Treat numeric 0 as an observed zero, not as missing data.\n"
            "Only describe a field as missing if it is null or the literal string 'unknown'.\n"
            "If the roster shows zero players in the target family and position quality is not unknown, "
            "say that no listed players in that family were found; do not say the count was unavailable.\n"
            "If the evidence is thin, keep the base fit unchanged and say so.\n"
            "You may adjust the interpretation by at most one fit level.\n"
            "Write a fit_summary (2-3 sentences on overall fit), program_summary (program context), "
            "roster_summary (roster composition and openings), opportunity_summary (playing time outlook), "
            "and trend_summary (program trajectory). Keep each under 100 words.\n"
            "Populate reasons_for_fit with 2-4 bullet points and risks with 1-3 bullet points."
        )

    def _review_input(
        self,
        school: Dict[str, Any],
        player_stats: Dict[str, Any],
        baseball_assessment: Dict[str, Any],
        academic_score: Dict[str, Any],
        evidence: GatheredEvidence,
    ) -> str:
        athletic_match = {
            "baseball_fit": school.get("fit_label") or school.get("baseball_fit"),
            "academic_fit": school.get("academic_fit"),
            "delta": school.get("delta"),
            "school_sci": school.get("sci"),
            "ranking_adjustment": school.get("ranking_adjustment"),
            "metric_comparisons": school.get("metric_comparisons", []),
        }
        program_trend = {
            "trend_bonus": school.get("trend_bonus"),
            "trend": school.get("trend"),
            "conference": school.get("conference"),
        }
        payload = {
            "player": {
                "primary_position": player_stats.get("primary_position"),
                "position_family": _school_position_family(player_stats.get("primary_position", "")),
                "archetype": _player_archetype(player_stats),
                "height": player_stats.get("height"),
                "weight": player_stats.get("weight"),
                "exit_velo_max": player_stats.get("exit_velo_max"),
                "sixty_time": player_stats.get("sixty_time"),
                "inf_velo": player_stats.get("inf_velo"),
                "of_velo": player_stats.get("of_velo"),
                "c_velo": player_stats.get("c_velo"),
                "pop_time": player_stats.get("pop_time"),
            },
            "baseball_assessment": baseball_assessment,
            "academic_score": academic_score,
            "athletic_match": athletic_match,
            "program_trend": program_trend,
            "evidence": evidence.model_dump(),
        }
        return (
            "Review this school using the provided evidence packet only.\n"
            f"{json.dumps(payload)}"
        )


__all__ = [
    "DeepSchoolInsightService",
    "compute_raw_opportunity_signal",
    "compute_ranking_adjustment",
    "compute_ranking_score",
    "compute_roster_label",
]


def _research_error_message(prefix: str, exc: Exception) -> str:
    message = " ".join(str(exc).split())
    if len(message) > 200:
        message = message[:197] + "..."
    return f"{prefix}: {exc.__class__.__name__}: {message}" if message else f"{prefix}: {exc.__class__.__name__}"


def _is_retryable(exc: Exception) -> bool:
    """Return True for transient errors worth retrying."""
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return True
    exc_type = type(exc).__name__.lower()
    exc_str = str(exc).lower()
    if "connection" in exc_type or "connection" in exc_str:
        return True
    if "ratelimit" in exc_type or "rate_limit" in exc_str or "429" in exc_str:
        return True
    if any(code in exc_str for code in ("500", "502", "503", "server_error")):
        return True
    if "apiconnection" in exc_type or "apitimeout" in exc_type:
        return True
    return False
