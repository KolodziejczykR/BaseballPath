from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

@dataclass
class UserPreferences:
    """Data class for user preferences in college selection"""
    # Geographic preferences
    preferred_regions: Optional[List[str]] = None  # e.g., ["Southeast", "Northeast", "Midwest", "West"]
    
    # Academic preferences
    min_academic_rating: Optional[str] = None      # e.g., "B+", "A-"
    preferred_school_size: Optional[str] = None    # e.g., "Small", "Medium", "Large"
    
    # Financial constraints
    max_tuition_budget: Optional[int] = None       # dollars per year
    financial_aid_important: bool = False
    
    # Athletic preferences
    min_athletics_rating: Optional[str] = None     # e.g., "B", "A-"
    playing_time_priority: str = "Medium"          # "High", "Medium", "Low"
    
    # Campus life preferences
    campus_life_important: bool = False
    party_scene_preference: Optional[str] = None   # e.g., "Active", "Moderate", "Quiet"
    
    # Academic performance
    gpa: Optional[float] = None                    # Student's GPA
    graduation_year: Optional[str] = None          # e.g., "2026"
    
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