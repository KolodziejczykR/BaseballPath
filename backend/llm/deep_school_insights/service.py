"""Orchestration façade for deep school insight enrichment.

``DeepSchoolInsightService`` glues the split modules (parsers, evidence,
fetch, ranking, llm_review) together and drives the per-batch enrichment
loop used by Celery. The individual steps are thin wrappers around the pure
functions in this package so that tests and scripts can still call them on
a bare service instance created via ``__new__``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import httpx
from bs4 import BeautifulSoup
from openai import AsyncOpenAI

from .evidence import (
    _empty_evidence,
    _has_meaningful_evidence,
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
    _trusted_domains_for_school,
    clean_soup,
    match_players_to_stats,
    parse_roster_players,
    parse_stats_records,
)
from .ranking import (
    MAX_RERANK_ADJUSTMENT,
    RESEARCH_QUALITY_BONUS,
    _apply_cross_school_reranking,
    _cross_school_sort_key,
    compute_ranking_adjustment,
    compute_ranking_score,
    compute_roster_label,
)
from .types import (
    DeepSchoolInsight,
    DeepSchoolReview,
    GatheredEvidence,
    MatchedPlayer,
    ParsedPlayer,
    ParsedStatLine,
)


logger = logging.getLogger(__name__)


class DeepSchoolInsightService:
    def __init__(
        self,
        client: Optional[AsyncOpenAI] = None,
        initial_batch_size: int = 10,
        batch_size: int = 10,
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
        ranking_priority: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not self.enabled or self.client is None or not schools:
            return schools

        t_enrich_start = time.monotonic()
        logger.info(
            "[TIMING] enrich_and_rerank start schools=%d initial_batch=%d batch=%d",
            len(schools), self.initial_batch_size, self.batch_size,
        )
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
        batch_index = 0

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

            batch_index += 1
            t_batch_start = time.monotonic()
            logger.info(
                "[TIMING] batch start idx=%d size=%d schools=%s",
                batch_index,
                len(next_batch),
                [s.get("school_name") for s in next_batch],
            )
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
            logger.info(
                "[TIMING] batch done idx=%d size=%d elapsed=%.2fs",
                batch_index, len(next_batch), time.monotonic() - t_batch_start,
            )
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

        player_academic_score: Optional[float] = None
        if isinstance(academic_score, dict):
            raw_score = academic_score.get("effective")
            if raw_score is None:
                raw_score = academic_score.get("composite")
            if raw_score is not None:
                try:
                    player_academic_score = float(raw_score)
                except (TypeError, ValueError):
                    player_academic_score = None

        _apply_cross_school_reranking(
            schools_copy,
            ranking_priority=ranking_priority,
            player_academic_score=player_academic_score,
        )
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
            MAX_ACAD_STRONG_SAFETY = 0 if ranking_priority == "academics" else 5

            strong_safeties = [s for s in schools_copy if s.get("fit_label") == "Strong Safety"]
            strong_reaches = [s for s in schools_copy if s.get("fit_label") == "Strong Reach"]
            rest = [s for s in schools_copy if s.get("fit_label") not in ("Strong Safety", "Strong Reach")]

            for group in (strong_safeties, strong_reaches, rest):
                group.sort(key=_cross_school_sort_key, reverse=True)

            selected = list(rest)
            selected.extend(strong_safeties[:MAX_STRONG_SAFETY])
            selected.extend(strong_reaches[:MAX_STRONG_REACH])
            selected.sort(key=_cross_school_sort_key, reverse=True)

            acad_ss_count = 0
            acad_capped: list = []
            for s in selected:
                if (s.get("academic_fit") or "").strip() == "Strong Safety":
                    acad_ss_count += 1
                    if acad_ss_count <= MAX_ACAD_STRONG_SAFETY:
                        acad_capped.append(s)
                else:
                    acad_capped.append(s)

            trimmed = acad_capped[:final_limit]

            # Guarantee priority-specific schools appear in the final set.
            # "academics" → inject top academic schools (by selectivity score)
            # "baseball_fit" → inject top baseball schools (by SCI)
            GUARANTEED_SLOTS = 3
            TOP_POOL = 10

            if ranking_priority == "academics":
                top_academic = sorted(
                    schools_copy,
                    key=lambda s: float(s.get("academic_selectivity_score") or 0),
                    reverse=True,
                )[:TOP_POOL]
                trimmed_names = {s.get("school_name") for s in trimmed}
                missing = [s for s in top_academic if s.get("school_name") not in trimmed_names]
                for s in missing[:GUARANTEED_SLOTS]:
                    if len(trimmed) >= final_limit:
                        trimmed.pop()  # drop lowest-ranked school
                    trimmed.append(s)
                trimmed.sort(key=_cross_school_sort_key, reverse=True)

            elif ranking_priority == "baseball_fit":
                top_baseball = sorted(
                    schools_copy,
                    key=lambda s: float(s.get("sci") or 0),
                    reverse=True,
                )[:TOP_POOL]
                trimmed_names = {s.get("school_name") for s in trimmed}
                missing = [s for s in top_baseball if s.get("school_name") not in trimmed_names]
                for s in missing[:GUARANTEED_SLOTS]:
                    if len(trimmed) >= final_limit:
                        trimmed.pop()  # drop lowest-ranked school
                    trimmed.append(s)
                trimmed.sort(key=_cross_school_sort_key, reverse=True)

            schools_copy = trimmed

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
        logger.info(
            "[TIMING] enrich_and_rerank done researched=%d final=%d batches=%d total=%.2fs",
            len(researched_ids),
            len(schools_copy),
            batch_index,
            time.monotonic() - t_enrich_start,
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

        # Human-facing narrative fields
        school["why_this_school"] = insight.review.why_this_school
        school["school_snapshot"] = insight.review.school_snapshot
        school["considerations"] = insight.review.considerations

        # Backward-compat: populate fit_summary / school_description so any
        # code or UI that still references the old field names keeps working.
        if insight.review.why_this_school:
            school["fit_summary"] = insight.review.why_this_school
        if insight.review.school_snapshot:
            school["school_description"] = insight.review.school_snapshot

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
                    why_this_school="",
                    school_snapshot="",
                    considerations=[],
                    data_gaps=[
                        "Deep roster research is unavailable because the running OpenAI SDK does not support responses.parse."
                    ],
                ),
                ranking_adjustment=0.0,
                ranking_score=compute_ranking_score(float(school.get("delta") or 0.0), 0.0),
                research_status="unavailable",
            )

        school_name = school.get("display_school_name") or school.get("school_name") or "Unknown"
        t_school_start = time.monotonic()
        trusted_domains = _trusted_domains_for_school(school)
        evidence = await self._gather_evidence(school, player_stats, trusted_domains)
        t_evidence_done = time.monotonic()
        logger.info(
            "[TIMING] enrich_single evidence school=%r elapsed=%.2fs",
            school_name, t_evidence_done - t_school_start,
        )
        if not _has_meaningful_evidence(evidence):
            logger.info(
                "[TIMING] enrich_single school=%r status=insufficient_evidence total=%.2fs",
                school_name, time.monotonic() - t_school_start,
            )
            return DeepSchoolInsight(
                school_name=school.get("school_name", ""),
                evidence=evidence,
                review=DeepSchoolReview(
                    base_athletic_fit=school.get("fit_label") or "",
                    opportunity_fit="",
                    final_school_view=school.get("fit_label") or "",
                    adjustment_from_base="none",
                    confidence="low",
                    why_this_school="",
                    school_snapshot="",
                    considerations=[],
                    data_gaps=evidence.data_gaps,
                ),
                ranking_adjustment=0.0,
                ranking_score=compute_ranking_score(float(school.get("delta") or 0.0), 0.0),
                research_status="insufficient_evidence",
            )

        t_review_start = time.monotonic()
        review = await self._review_school(school, player_stats, baseball_assessment, academic_score, evidence)
        t_review_done = time.monotonic()
        logger.info(
            "[TIMING] enrich_single review school=%r elapsed=%.2fs status=%s total=%.2fs",
            school_name,
            t_review_done - t_review_start,
            "ok" if review is not None else "failed",
            t_review_done - t_school_start,
        )
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
                why_this_school="",
                school_snapshot="",
                considerations=[],
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

    # ------------------------------------------------------------------
    # Thin wrapper methods — delegate to the package-level pure functions.
    # Preserved as instance methods so that tests and scripts that call
    # ``DeepSchoolInsightService.__new__(cls)._compute_evidence(...)`` keep
    # working without any refactor on their end.
    # ------------------------------------------------------------------

    def _httpx_client(self) -> httpx.AsyncClient:
        return make_httpx_client()

    def _parse_roster_players(self, soup: BeautifulSoup) -> List[ParsedPlayer]:
        return parse_roster_players(soup)

    def _parse_stats_records(self, soup: BeautifulSoup) -> List[ParsedStatLine]:
        return parse_stats_records(soup)

    def _match_players_to_stats(
        self,
        players: List[ParsedPlayer],
        stats: List[ParsedStatLine],
    ) -> List[MatchedPlayer]:
        return match_players_to_stats(players, stats)

    def _compute_evidence(
        self,
        matched_players: List[MatchedPlayer],
        player_stats: Dict[str, Any],
        roster_url: str,
        stats_available: bool,
    ) -> GatheredEvidence:
        return compute_evidence(matched_players, player_stats, roster_url, stats_available)

    @staticmethod
    def _clean_soup(html: str) -> BeautifulSoup:
        return clean_soup(html)

    async def _fetch_and_parse_roster(
        self, school: Dict[str, Any],
    ) -> Tuple[List[ParsedPlayer], Optional[str]]:
        return await fetch_and_parse_roster(school)

    async def _fetch_and_parse_stats(self, school: Dict[str, Any]) -> List[ParsedStatLine]:
        return await fetch_and_parse_stats(school)

    async def _gather_evidence(
        self,
        school: Dict[str, Any],
        player_stats: Dict[str, Any],
        trusted_domains: Sequence[str],
    ) -> GatheredEvidence:
        return await gather_evidence(school, player_stats, trusted_domains)

    async def _review_school(
        self,
        school: Dict[str, Any],
        player_stats: Dict[str, Any],
        baseball_assessment: Dict[str, Any],
        academic_score: Dict[str, Any],
        evidence: GatheredEvidence,
        _max_retries: int = 2,
    ) -> Optional[DeepSchoolReview]:
        school_name = school.get("display_school_name") or school.get("school_name") or "?"
        for attempt in range(_max_retries + 1):
            result = await review_school(
                school,
                player_stats,
                baseball_assessment,
                academic_score,
                evidence,
                responses_parse=self._responses_parse,
                review_model=self.review_model,
            )
            if result is not None:
                return result
            if attempt < _max_retries:
                wait = 2.0 * (attempt + 1)
                logger.warning(
                    "LLM review failed for %r (attempt %d/%d), retrying in %.0fs",
                    school_name, attempt + 1, _max_retries + 1, wait,
                )
                await asyncio.sleep(wait)
        return None

    def _review_instructions(self) -> str:
        return review_instructions()

    def _review_input(
        self,
        school: Dict[str, Any],
        player_stats: Dict[str, Any],
        baseball_assessment: Dict[str, Any],
        academic_score: Dict[str, Any],
        evidence: GatheredEvidence,
    ) -> str:
        return review_input(school, player_stats, baseball_assessment, academic_score, evidence)


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
