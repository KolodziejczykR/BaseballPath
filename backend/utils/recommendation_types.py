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
class SortScores:
    academic_grade: Optional[str] = None
    nice_to_have_count: int = 0


@dataclass
class LLMReasoning:
    summary: Optional[str] = None
    fit_qualities: List[str] = field(default_factory=list)
    cautions: List[str] = field(default_factory=list)


@dataclass
class RelaxSuggestion:
    preference: str
    suggestion: str
    reason: str


@dataclass
class RecommendationSummary:
    player_summary: Optional[str] = None
    relax_suggestions: List[RelaxSuggestion] = field(default_factory=list)
    low_result_flag: bool = False
    llm_enabled: bool = False
    llm_job_id: Optional[str] = None
    llm_status: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def school_recommendation_from_dict(data: Dict[str, Any]) -> "SchoolRecommendation":
    return SchoolRecommendation(
        school_name=data.get("school_name"),
        school_logo_image=data.get("school_logo_image"),
        division_group=data.get("division_group"),
        division_label=data.get("division_label"),
        location=SchoolLocation(**(data.get("location") or {})),
        size=SchoolSize(**(data.get("size") or {})),
        academics=AcademicsInfo(**(data.get("academics") or {})),
        athletics=AthleticsInfo(**(data.get("athletics") or {})),
        student_life=StudentLifeInfo(**(data.get("student_life") or {})),
        financial=FinancialInfo(**(data.get("financial") or {})),
        overall_grade=data.get("overall_grade"),
        match_analysis=MatchAnalysis(
            total_nice_to_have_matches=(data.get("match_analysis") or {}).get(
                "total_nice_to_have_matches", 0
            ),
            pros=[
                MatchPoint(**item)
                for item in (data.get("match_analysis") or {}).get("pros", [])
            ],
            cons=[
                MatchMiss(**item)
                for item in (data.get("match_analysis") or {}).get("cons", [])
            ],
        ),
        scores=SortScores(**(data.get("scores") or {})),
        llm_reasoning=(
            LLMReasoning(**data["llm_reasoning"])
            if data.get("llm_reasoning") is not None
            else None
        ),
    )


@dataclass
class SchoolRecommendation:
    school_name: str
    school_logo_image: Optional[str] = None
    division_group: Optional[str] = None
    division_label: Optional[str] = None
    location: SchoolLocation = field(default_factory=SchoolLocation)
    size: SchoolSize = field(default_factory=SchoolSize)
    academics: AcademicsInfo = field(default_factory=AcademicsInfo)
    athletics: AthleticsInfo = field(default_factory=AthleticsInfo)
    student_life: StudentLifeInfo = field(default_factory=StudentLifeInfo)
    financial: FinancialInfo = field(default_factory=FinancialInfo)
    overall_grade: Optional[str] = None
    match_analysis: MatchAnalysis = field(default_factory=MatchAnalysis)
    scores: SortScores = field(default_factory=SortScores)
    llm_reasoning: Optional[LLMReasoning] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
