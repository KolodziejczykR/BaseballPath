from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

@dataclass
class NicheRatings:
    """Data class for Niche.com college ratings and information"""
    school_name: str
    overall_grade: str = None
    academics_grade: str = None
    campus_life_grade: str = None
    overall_athletics_grade: str = None
    value_grade: str = None
    student_life_grade: str = None
    party_scene_grade: str = None
    diversity_grade: str = None
    location_grade: str = None
    safety_grade: str = None
    professors_grade: str = None
    dorms_grade: str = None
    campus_food_grade: str = None
    enrollment: str = None
    niche_url: str = None
    error: str = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
@dataclass
class SchoolStatisticsAPI:
    """Data class for school statistics, from CollegeScorecard API"""
    school_city: str
    undergrad_enrollment: int
    in_state_tuition: int
    out_of_state_tuition: int
    admission_rate: float
    avg_sat: int
    avg_act: int

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class SchoolInformation:
    """Data class for the school, to be sent to LLM as extra context"""
    school_name: str
    school_stats: SchoolStatisticsAPI
    niche_ratings: NicheRatings

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "school_name": self.school_name,
            "school_stats": self.school_stats.to_dict(),
            "niche_ratings": self.niche_ratings.to_dict()
        }