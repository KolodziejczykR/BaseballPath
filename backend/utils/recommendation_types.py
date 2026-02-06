"""
Final response schema types for school recommendations.

These types represent the frontend-facing payload for each recommended school.
They are intentionally decoupled from internal SchoolMatch objects.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class SchoolLocation:
    state: Optional[str] = None
    region: Optional[str] = None


@dataclass
class SchoolSize:
    enrollment: Optional[int] = None
    category: Optional[str] = None


@dataclass
class AcademicsInfo:
    grade: Optional[str] = None
    avg_sat: Optional[int] = None
    avg_act: Optional[int] = None
    admission_rate: Optional[float] = None


@dataclass
class AthleticsInfo:
    grade: Optional[str] = None


@dataclass
class StudentLifeInfo:
    grade: Optional[str] = None
    party_scene_grade: Optional[str] = None


@dataclass
class FinancialInfo:
    in_state_tuition: Optional[int] = None
    out_of_state_tuition: Optional[int] = None


@dataclass
class MatchPoint:
    preference: str
    description: str
    category: str


@dataclass
class MatchMiss:
    preference: str
    reason: str
    category: str


@dataclass
class MatchAnalysis:
    total_nice_to_have_matches: int = 0
    pros: List[MatchPoint] = field(default_factory=list)
    cons: List[MatchMiss] = field(default_factory=list)


@dataclass
class PlayingTimeInfo:
    available: bool
    z_score: Optional[float] = None
    percentile: Optional[float] = None
    bucket: Optional[str] = None
    bucket_description: Optional[str] = None
    interpretation: Optional[str] = None
    breakdown: Optional[Dict[str, float]] = None
    player_strength: Optional[str] = None
    team_needs: Optional[str] = None
    program_trend: Optional[str] = None
    message: Optional[str] = None


@dataclass
class SortScores:
    playing_time_score: Optional[float] = None
    academic_grade: Optional[str] = None
    nice_to_have_count: int = 0


@dataclass
class LLMReasoning:
    summary: Optional[str] = None
    fit_qualities: List[str] = field(default_factory=list)
    cautions: List[str] = field(default_factory=list)


@dataclass
class SchoolRecommendation:
    school_name: str
    division_group: Optional[str] = None
    location: SchoolLocation = field(default_factory=SchoolLocation)
    size: SchoolSize = field(default_factory=SchoolSize)
    academics: AcademicsInfo = field(default_factory=AcademicsInfo)
    athletics: AthleticsInfo = field(default_factory=AthleticsInfo)
    student_life: StudentLifeInfo = field(default_factory=StudentLifeInfo)
    financial: FinancialInfo = field(default_factory=FinancialInfo)
    overall_grade: Optional[str] = None
    match_analysis: MatchAnalysis = field(default_factory=MatchAnalysis)
    playing_time: PlayingTimeInfo = field(default_factory=lambda: PlayingTimeInfo(available=False))
    scores: SortScores = field(default_factory=SortScores)
    llm_reasoning: Optional[LLMReasoning] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
