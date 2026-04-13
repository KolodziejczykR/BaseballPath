"""Deterministic evidence computation for a single school.

Takes parsed roster/stats data and produces a ``GatheredEvidence`` packet that
the LLM reviewer interprets. Also hosts the domain helpers (position family,
enrollment timing, safety/meaningfulness checks) shared by other modules in
this package.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Any, Dict, List, Optional

from backend.roster_scraper.roster_parser import normalize_position

from .types import (
    GatheredEvidence,
    HIGH_USAGE_GS_THRESHOLD,
    MatchedPlayer,
    OpportunityContext,
    RecruitingContext,
    ResearchSource,
    RosterContext,
)


def _safe_int(value: Optional[int]) -> int:
    try:
        if value is None:
            return 0
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


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


def _current_academic_year() -> int:
    """Return the academic year for the current roster season.

    Rosters published before August reflect the upcoming academic year
    (spring season), so we use the calendar year directly.
    """
    return date.today().year


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


def _years_until_enrollment(player_stats: Dict[str, Any]) -> int:
    """How many roster turnover cycles before the player arrives on campus.

    Capped at 3 because beyond that the entire roster will have turned over
    and further projection adds no value.
    """
    enrollment_year = _target_incoming_grad_year(player_stats)
    return min(3, max(0, enrollment_year - _current_academic_year()))


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
    if departure_ratio >= 0.3:
        return "high"
    if departure_ratio >= 0.15:
        return "medium"
    return "low"


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


def _estimate_competition(total: int, returning_starters: Optional[int], underclassmen: int) -> str:
    if total == 0:
        return "unknown"
    if returning_starters is not None:
        if returning_starters >= 5:
            return "high"
        if returning_starters >= 3:
            return "medium"
        return "low"
    if total >= 8 and underclassmen >= 4:
        return "high"
    if total >= 5:
        return "medium"
    return "low"


def compute_evidence(
    matched_players: List[MatchedPlayer],
    player_stats: Dict[str, Any],
    roster_url: str,
    stats_available: bool,
) -> GatheredEvidence:
    """Build GatheredEvidence deterministically from parsed roster/stats data.

    Projections are shifted forward by the player's years until enrollment
    so that departures, upperclassmen/underclassmen counts, and opportunity
    estimates reflect the roster the player will actually face on arrival.
    """
    target_family = _school_position_family(player_stats.get("primary_position", ""))
    target_position = normalize_position(player_stats.get("primary_position", ""))
    years_out = _years_until_enrollment(player_stats)
    enrollment_year = _target_incoming_grad_year(player_stats)

    same_family = [m for m in matched_players if m.player.position_family == target_family]
    same_exact = [m for m in matched_players if m.player.position_normalized == target_position] if target_position else []

    def _will_depart(m: MatchedPlayer) -> bool:
        cy = m.player.normalized_class_year or 0
        if cy == 0:
            return False
        effective = cy - (1 if m.player.is_redshirt else 0)
        return effective + years_out >= 4

    departures_family = sum(1 for m in same_family if _will_depart(m))
    departures_exact = (
        sum(1 for m in same_exact if _will_depart(m))
        if same_exact else None
    )

    remaining_family = [m for m in same_family if not _will_depart(m)]

    def _projected_year(m: MatchedPlayer) -> int:
        return (m.player.normalized_class_year or 0) + years_out

    upperclassmen = sum(1 for m in remaining_family if _projected_year(m) >= 3)
    underclassmen = sum(1 for m in remaining_family if 1 <= _projected_year(m) <= 2)

    transfers_family = sum(
        1 for m in same_family
        if m.player.previous_school is not None
    )

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

    returning_high_usage_family = 0
    returning_high_usage_exact = 0
    if stats_available:
        for m in remaining_family:
            stat = m.batting_stats or m.pitching_stats
            if stat and stat.games_started >= HIGH_USAGE_GS_THRESHOLD:
                returning_high_usage_family += 1
                if target_position and m.player.position_normalized == target_position:
                    returning_high_usage_exact += 1

    opener_family = _estimate_openings(
        departures=departures_family,
        total=len(same_family),
        returning_high_usage=returning_high_usage_family if stats_available else None,
    )
    opener_exact = _estimate_openings(
        departures=departures_exact or 0,
        total=len(same_exact),
        returning_high_usage=returning_high_usage_exact if stats_available else None,
    ) if same_exact else "unknown"

    opportunity = _estimate_opportunity(
        departures=departures_family,
        total=len(same_family),
        returning_starters=returning_high_usage_family if stats_available else None,
    )
    competition = _estimate_competition(
        total=len(remaining_family),
        returning_starters=returning_high_usage_family if stats_available else None,
        underclassmen=underclassmen,
    )

    notes: List[str] = []
    if years_out > 0:
        notes.append(
            f"Projected {years_out} year(s) forward ({enrollment_year} enrollment): "
            f"{departures_family} of {len(same_family)} {target_family} players "
            f"will have graduated by arrival."
        )
    if not stats_available:
        notes.append("Stats page was not available; estimates based on roster data only.")
    if pos_quality == "family_only":
        notes.append("Position listings use broad categories (IF/OF/P); exact positions unknown.")
    if pos_quality != "unknown" and not same_family:
        notes.append(f"No listed players matched the {target_family} position family on the roster.")

    projected_note: Optional[str] = None
    if years_out >= 3:
        projected_note = (
            f"Player enrolls in {enrollment_year} — current roster will be almost "
            f"entirely turned over by then. Program size ({len(same_family)} {target_family} "
            f"players) and recruiting patterns are more relevant than specific player analysis."
        )
    elif years_out > 0:
        projected_note = (
            f"Player enrolls in {enrollment_year} ({years_out} year(s) out). "
            f"{departures_family} of {len(same_family)} current {target_family} players "
            f"projected to depart; {len(remaining_family)} will remain on roster at arrival."
        )

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
    if years_out >= 3:
        data_gaps.append(
            f"Player enrolls in {enrollment_year} — current roster will be almost entirely "
            f"turned over by then. Program size and recruiting patterns are more relevant "
            f"than specific player analysis."
        )

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
            projected_years_out=years_out,
            projected_departures_note=projected_note,
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
