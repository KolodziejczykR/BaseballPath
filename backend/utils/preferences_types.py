from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

VALID_GRADES = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F"]

@dataclass
class UserPreferences:
    """Data class for user preferences in college selection"""
    max_budget: int = None                          # max tuition budget BEFORE AID
    financial_aid_important: bool = False
    user_state: str = None                          # e.g., "CA", "NY", "TX"
    admit_rate_floor: Optional[int] = None          # 0–100 (%)
    min_academic_rating: Optional[str] = None       # e.g., "B+", "A-"

    preferred_school_size: Optional[List[str]] = None     # "Small" (0-2999 students), "Medium" (3000-9999 students), "Large" (10000-29999 students), "Very Large" (30000+ students)
    gpa: Optional[float] = None                           # Student's GPA (out of 4.0)
    sat: Optional[int] = None                             # Student's SAT score (out of 1600)
    act: Optional[int] = None                             # Student's ACT score (out of 36)
    hs_graduation_year: Optional[int] = None              # e.g., 2027
    intended_major_buckets: Optional[str] = None          # e.g., "Engineering", "Business", "Healthcare", "Social Sciences", "Arts", "Undecided" (allow multiple selections)
    academic_env_preference: Optional[str] = None            # High-academic|Balanced|Flexible

    # Geographic preferences, interactive map that you can click on states to select
    preferred_states: Optional[List[str]] = None
    preferred_regions: Optional[List[str]] = None        # e.g., "Northeast", "Mid-Atlantic", "Midwest", "South", "West"
    party_scene_preference: Optional[str] = None   # e.g., "Active" (A+ through A-), "Moderate" (B+ through B-), "Quiet" (C+ and below)
    
    # Athletic preferences
    min_athletics_rating: Optional[str] = None     # e.g., "B", "A-"
    playing_time_priority: Optional[str] = None    # "High", "Medium", "Low"
    athletics_env_preference: Optional[str] = None       # High-profile | Balanced | Doesn't matter
    
    pbr_profile_link: Optional[str] = None
    perfect_game_profile_link: Optional[str] = None

    def __post_init__(self):
        """Validate admit_rate_floor after initialization"""
        if self.admit_rate_floor is not None:
            if self.admit_rate_floor < 0:
                raise ValueError("admin rate floor cannot be below 0")
            if self.admit_rate_floor > 100:
                raise ValueError("admin rate floor cannot be above 100")
            
        if self.min_academic_rating is not None and self.min_academic_rating not in VALID_GRADES:
            raise ValueError(f"min_academic_rating must be one of {VALID_GRADES}")
        
        if self.min_athletics_rating is not None and self.min_athletics_rating not in VALID_GRADES:
            raise ValueError(f"min_athletics_rating must be one of {VALID_GRADES}")
    
    def __setattr__(self, name, value):
        """Validate admit_rate_floor whenever it's set"""
        if name == 'admit_rate_floor' and value is not None:
            if value < 0:
                raise ValueError("admit rate floor cannot be below 0")
            if value > 100:
                raise ValueError("admit rate floor cannot be above 100")
        super().__setattr__(name, value)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

@dataclass
class PreferencesRequest:
    """Request model for preferences endpoint"""
    preferences: UserPreferences
    player_position: str  # To potentially customize preferences by position
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "preferences": self.preferences.to_dict(),
            "player_position": self.player_position
        }

@dataclass
class PreferencesResponse:
    """Response model for preferences endpoint"""
    message: str
    preferences_received: UserPreferences
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "message": self.message,
            "preferences_received": self.preferences_received.to_dict()
        }