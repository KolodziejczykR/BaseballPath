from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict, field

VALID_GRADES = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F"]

@dataclass
class UserPreferences:
    """Data class for user preferences in college selection"""
    user_state: str                                 # e.g., "CA", "NY", "TX" - REQUIRED for tuition calculations
    max_budget: int = None                          # max tuition budget BEFORE AID
    admit_rate_floor: Optional[int] = None          # 0–100 (%)
    min_academic_rating: Optional[str] = None       # e.g., "B+", "A-"

    preferred_school_size: Optional[List[str]] = None     # "Small" (0-2999 students), "Medium" (3000-9999 students), "Large" (10000-29999 students), "Very Large" (30000+ students)
    gpa: Optional[float] = None                           # Student's GPA (out of 4.0)
    sat: Optional[int] = None                             # Student's SAT score (out of 1600)
    act: Optional[int] = None                             # Student's ACT score (out of 36)
    hs_graduation_year: Optional[int] = None              # e.g., 2027
    intended_major_buckets: Optional[str] = None          # e.g., "Engineering", "Business", "Healthcare", "Social Sciences", "Arts", "Undecided" (allow multiple selections)

    min_student_satisfaction_rating: Optional[str] = None      # e.g., "B+", "A-"

    # Geographic preferences, interactive map that you can click on states to select
    preferred_states: Optional[List[str]] = None
    preferred_regions: Optional[List[str]] = None        # e.g., "Northeast", "Midwest", "South", "West"
    party_scene_preference: Optional[List[str]] = None   # e.g., ["Active", "Moderate"] for multi-select: "Active" (A+, A-), "Moderate" (A- through B), "Quiet" (B- and below)
    
    # Athletic preferences
    min_athletics_rating: Optional[str] = None           # e.g., "B", "A-"
    playing_time_priority: Optional[List[str]] = None    # ["High", "Medium"] for multi-select: "High", "Medium", "Low"
    
    # Recruiting profile links
    pbr_profile_link: Optional[str] = None
    perfect_game_profile_link: Optional[str] = None

    # Must-have preference tracking (not exposed in API, managed internally)
    _must_have_preferences: Set[str] = field(default_factory=set, init=False)

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

        if self.min_student_satisfaction_rating is not None and self.min_student_satisfaction_rating not in VALID_GRADES:
            raise ValueError(f"min_student_satisfaction_rating must be one of {VALID_GRADES}")
        
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
        data = asdict(self)
        # Remove the internal _must_have_preferences field from serialization
        data.pop('_must_have_preferences', None)
        return data

    def to_dict_with_must_haves(self) -> Dict:
        """Convert to dictionary including must-have preference information"""
        data = self.to_dict()
        data['must_have_preferences'] = list(self._must_have_preferences)
        return data

    def make_must_have(self, preference_name: str) -> bool:
        """
        Mark a preference as must-have for filtering.

        Args:
            preference_name: Name of the preference field

        Returns:
            True if successfully marked as must-have, False if invalid preference name
        """
        # Get all valid preference field names, excluding user_state
        valid_preferences = {field.name for field in self.__dataclass_fields__.values()
                           if not field.name.startswith('_') and field.name != 'user_state'}

        if preference_name not in valid_preferences:
            return False

        # Don't allow marking preferences that are None as must-haves
        current_value = getattr(self, preference_name, None)
        if current_value is None:
            return False

        self._must_have_preferences.add(preference_name)
        return True

    def remove_must_have(self, preference_name: str) -> bool:
        """
        Remove a preference from must-have status.

        Args:
            preference_name: Name of the preference field

        Returns:
            True if successfully removed, False if not found
        """
        if preference_name in self._must_have_preferences:
            self._must_have_preferences.remove(preference_name)
            return True
        return False

    def get_must_haves(self) -> Dict[str, any]:
        """
        Get all preferences marked as must-have with their values.

        Returns:
            Dictionary of must-have preference names and values
        """
        must_haves = {}
        for pref_name in self._must_have_preferences:
            if pref_name == 'user_state':
                self.remove_must_have("user_state")
                continue
            value = getattr(self, pref_name, None)
            if value is not None:  # Only include non-None values
                must_haves[pref_name] = value
        return must_haves

    def get_nice_to_haves(self) -> Dict[str, any]:
        """
        Get all preferences NOT marked as must-have with their values.

        Returns:
            Dictionary of nice-to-have preference names and values
        """
        nice_to_haves = {}
        all_prefs = self.to_dict()

        for pref_name, value in all_prefs.items():
            if (pref_name not in self._must_have_preferences and
                    value is not None and
                    not pref_name.startswith('_') and
                    pref_name != 'user_state'):  # Exclude user_state - not a filterable preference
                nice_to_haves[pref_name] = value

        return nice_to_haves

    def is_must_have(self, preference_name: str) -> bool:
        """
        Check if a preference is marked as must-have.

        Args:
            preference_name: Name of the preference field

        Returns:
            True if marked as must-have, False otherwise
        """
        return preference_name in self._must_have_preferences

    def get_must_have_list(self) -> List[str]:
        """
        Get list of preference names marked as must-have.

        Returns:
            List of must-have preference names
        """
        return list(self._must_have_preferences)

    def set_must_haves_from_list(self, must_have_list: List[str]) -> List[str]:
        """
        Set must-have preferences from a list.
        Useful for deserializing from API requests.

        Args:
            must_have_list: List of preference names to mark as must-have

        Returns:
            List of preference names that couldn't be set as must-have
        """
        failed_prefs = []

        # Reset to empty (no mandatory must-haves)
        self._must_have_preferences = set()

        for pref_name in must_have_list:
            if not self.make_must_have(pref_name):
                failed_prefs.append(pref_name)

        return failed_prefs

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