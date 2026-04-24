"""Shared types for the deep school insights pipeline.

Pydantic models describe the evidence/review payloads exchanged with the LLM.
Dataclasses describe intermediate roster/stats parsing results that never cross
the network boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


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
    # --- Internal fields used by the ranking/reranking system ---
    base_athletic_fit: str = ""
    opportunity_fit: str = ""
    final_school_view: str = ""
    adjustment_from_base: Literal["none", "up_one", "down_one"] = "none"
    confidence: Literal["high", "medium", "low"] = "low"
    data_gaps: List[str] = Field(default_factory=list)

    # --- Human-facing narrative fields ---
    why_this_school: str = ""
    school_snapshot: str = ""
    considerations: List[str] = Field(default_factory=list)


# Pre-warm Pydantic schemas eagerly so the first LLM call doesn't eat a cold
# compilation penalty.
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
