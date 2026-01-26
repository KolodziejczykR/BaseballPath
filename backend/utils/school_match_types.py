"""
School match types for two-tier filtering system

This module defines data structures for the must-have vs nice-to-have
filtering system, allowing for dynamic school counting and detailed
match scoring.
"""

from typing import Dict, List, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from backend.playing_time.types import PlayingTimeResult


class PreferenceCategory(Enum):
    """Categories for different types of preferences"""
    MUST_HAVE = "must_have"
    NICE_TO_HAVE = "nice_to_have"


class NiceToHaveType(Enum):
    """Types of nice-to-have preferences for scoring"""
    GEOGRAPHIC = "geographic"
    ACADEMIC_FIT = "academic_fit"
    SCHOOL_CHARACTERISTICS = "school_characteristics"
    ATHLETIC_PREFERENCES = "athletic_preferences"
    DEMOGRAPHIC = "demographic"


@dataclass
class NiceToHaveMatch:
    """Represents a single nice-to-have preference match"""
    preference_type: NiceToHaveType
    preference_name: str
    user_value: Any
    school_value: Any
    description: str  # Human-readable description of the match


@dataclass
class NiceToHaveMiss:
    """Represents a single nice-to-have preference that did NOT match"""
    preference_type: NiceToHaveType
    preference_name: str
    user_value: Any
    school_value: Any
    reason: str  # Human-readable explanation of why it didn't match


@dataclass
class SchoolMatch:
    """
    Represents a school that meets must-have requirements with
    nice-to-have preference matching details and baseball rankings data
    """
    school_name: str
    school_data: Dict[str, Any]  # Full school information from database
    division_group: str  # Non-D1, Non-P4 D1, Power 4 D1

    # Nice-to-have matching
    nice_to_have_matches: List[NiceToHaveMatch] = field(default_factory=list)
    nice_to_have_misses: List[NiceToHaveMiss] = field(default_factory=list)

    # Baseball rankings integration
    baseball_strength: Optional[Dict[str, Any]] = None  # From BaseballRankingsIntegration
    playing_time_factor: Optional[float] = None  # DEPRECATED: use playing_time_result instead
    has_baseball_data: bool = False  # Whether baseball rankings are available

    # Playing time analysis (comprehensive result from PlayingTimeCalculator)
    playing_time_result: Optional["PlayingTimeResult"] = None

    def add_nice_to_have_match(self, match: NiceToHaveMatch):
        """Add a nice-to-have match"""
        self.nice_to_have_matches.append(match)

    def add_nice_to_have_miss(self, miss: NiceToHaveMiss):
        """Add a nice-to-have miss (non-match)"""
        self.nice_to_have_misses.append(miss)


    def get_match_summary(self) -> Dict[str, Any]:
        """Get a simplified summary of matches and misses for display"""
        summary = {
            "school_name": self.school_name,
            "division_group": self.division_group,
            "total_nice_to_have_matches": len(self.nice_to_have_matches),
            "pros": [
                {
                    "preference": match.preference_name,
                    "description": match.description
                }
                for match in self.nice_to_have_matches
            ],
            "cons": [
                {
                    "preference": miss.preference_name,
                    "reason": miss.reason
                }
                for miss in self.nice_to_have_misses
            ]
        }

        # Add baseball strength if available
        if self.has_baseball_data and self.baseball_strength:
            summary["baseball_strength"] = {
                "has_data": True,
                "team_name": self.baseball_strength.get("team_name"),
                "strength_classification": self.baseball_strength.get("strength_classification"),
                "current_season": self.baseball_strength.get("current_season"),
                "trend": self.baseball_strength.get("trend_analysis", {}).get("trend")
            }
        else:
            summary["baseball_strength"] = {"has_data": False}

        # Add playing time analysis if available
        if self.playing_time_result is not None:
            summary["playing_time"] = self.playing_time_result.to_summary_dict()
        else:
            summary["playing_time"] = {"has_data": False}

        return summary


@dataclass
class FilteringResult:
    """Result of the two-tier filtering process"""
    must_have_count: int  # Number of schools meeting must-haves
    school_matches: List[SchoolMatch]  # Schools with nice-to-have scoring
    total_possible_schools: int  # Total schools in database for this division
    filtering_summary: Dict[str, int]  # How many schools filtered at each step

    def get_top_matches(self, limit: int = 20) -> List[SchoolMatch]:
        """Get top N matches sorted by number of nice-to-have matches"""
        return sorted(self.school_matches,
                     key=lambda x: len(x.nice_to_have_matches), reverse=True)[:limit]


# NOTE: MUST_HAVE_PREFERENCES is now dynamic - users control via UserPreferences.make_must_have()
# This old hardcoded list is no longer used

NICE_TO_HAVE_MAPPING = {
    # Geographic preferences
    'preferred_states': NiceToHaveType.GEOGRAPHIC,
    'preferred_regions': NiceToHaveType.GEOGRAPHIC,

    # Academic fit preferences
    'sat': NiceToHaveType.ACADEMIC_FIT,
    'act': NiceToHaveType.ACADEMIC_FIT,
    'min_academic_rating': NiceToHaveType.ACADEMIC_FIT,
    'min_student_satisfaction_rating': NiceToHaveType.ACADEMIC_FIT,

    # School characteristics
    'preferred_school_size': NiceToHaveType.SCHOOL_CHARACTERISTICS,
    'party_scene_preference': NiceToHaveType.SCHOOL_CHARACTERISTICS,

    # Athletic preferences
    'min_athletics_rating': NiceToHaveType.ATHLETIC_PREFERENCES,

    # Demographic
    'hs_graduation_year': NiceToHaveType.DEMOGRAPHIC,
}