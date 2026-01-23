"""
Playing Time Calculator Types

Data structures for playing time calculation inputs and outputs.
Uses dataclasses for clean, type-safe structures with JSON serialization.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from enum import Enum


class PlayerStrength(Enum):
    """Categories for player's primary strength based on their best stat"""
    OFFENSIVE = "offensive"   # Best stat is exit_velo (power hitting)
    DEFENSIVE = "defensive"   # Best stat is position velocity or pop_time
    SPEED = "speed"           # Best stat is sixty_time


class TeamNeed(Enum):
    """Team's area of weakness based on Massey offensive/defensive ratings"""
    OFFENSE = "offense"       # Team's offense is weaker than defense
    DEFENSE = "defense"       # Team's defense is weaker than offense
    BALANCED = "balanced"     # No significant weakness


class ProgramTrend(Enum):
    """Program's trajectory based on multi-year rating changes"""
    IMPROVING = "improving"   # Rating decreased (got better) - more competition
    STABLE = "stable"         # Rating relatively unchanged
    DECLINING = "declining"   # Rating increased (got worse) - more opportunity


@dataclass
class StatZScore:
    """Z-score for a single stat with metadata"""
    stat_name: str
    raw_value: float
    z_score: float
    division_mean: float
    division_std: float
    is_inverted: bool = False  # True for stats where lower is better

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RankedStat:
    """A stat after ranking (best/mid/worst) with its weight"""
    stat_name: str
    z_score: float
    weight: float
    rank: str  # "best", "mid", or "worst"

    @property
    def weighted_contribution(self) -> float:
        """Calculate this stat's contribution to the final score"""
        return self.z_score * self.weight

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["weighted_contribution"] = self.weighted_contribution
        return result


@dataclass
class StatsBreakdown:
    """Breakdown of the stats component (75% of total score)"""
    best: RankedStat
    mid: RankedStat
    worst: RankedStat
    component_total: float
    player_strength: PlayerStrength

    # Individual z-scores before ranking
    all_z_scores: List[StatZScore] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "best": self.best.to_dict(),
            "mid": self.mid.to_dict(),
            "worst": self.worst.to_dict(),
            "component_total": self.component_total,
            "player_strength": self.player_strength.value,
            "all_z_scores": [z.to_dict() for z in self.all_z_scores],
        }


@dataclass
class PhysicalBreakdown:
    """Breakdown of the height/weight component (15% of total score)"""
    height_z: float
    weight_z: float
    average_z: float
    component_total: float

    # Raw values for context
    height_inches: float
    weight_lbs: float
    division_height_mean: float
    division_weight_mean: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MLBreakdown:
    """Breakdown of the ML prediction component (10% of total score)"""
    predicted_level: float      # Player's level on 0-100 scale
    school_level: float         # School's level on 0-100 scale
    gap: float                  # predicted_level - school_level
    component_total: float      # Final contribution to z-score

    # Input values for transparency
    d1_probability: float
    p4_probability: Optional[float]
    is_elite: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TeamFitBreakdown:
    """Breakdown of the team needs alignment bonus"""
    team_needs: TeamNeed
    team_offensive_rating: float
    team_defensive_rating: float
    player_strength: PlayerStrength
    best_stat_z: float
    alignment: bool             # True if player strength matches team need
    bonus: float                # Calculated bonus (0 to 0.20)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["team_needs"] = self.team_needs.value
        result["player_strength"] = self.player_strength.value
        return result


@dataclass
class TrendBreakdown:
    """Breakdown of the program trend bonus"""
    trend: ProgramTrend
    rating_change: Optional[float]  # Change in Massey rating over time
    years_span: Optional[str]       # e.g., "2023-2025"
    bonus: float

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["trend"] = self.trend.value
        return result


@dataclass
class PlayingTimeResult:
    """
    Complete result from the playing time calculation.

    This is the main output structure containing:
    - Final z-score and bucket classification
    - Percentile (statistical interpretation)
    - Detailed breakdown of all components
    - Human-readable interpretation
    """

    # Primary outputs
    final_z_score: float
    percentile: float           # Derived from z-score using normal CDF
    bucket: str                 # e.g., "Compete for Time"
    bucket_description: str     # e.g., "Top 16% - strong chance to earn spot"

    # Component breakdowns
    stats_breakdown: StatsBreakdown
    physical_breakdown: PhysicalBreakdown
    ml_breakdown: MLBreakdown
    team_fit_breakdown: TeamFitBreakdown
    trend_breakdown: TrendBreakdown

    # Context
    school_name: str
    school_division: str
    player_position: str

    # Human-readable summary
    interpretation: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "final_z_score": round(self.final_z_score, 3),
            "percentile": round(self.percentile, 1),
            "bucket": self.bucket,
            "bucket_description": self.bucket_description,
            "breakdown": {
                "stats": self.stats_breakdown.to_dict(),
                "physical": self.physical_breakdown.to_dict(),
                "ml": self.ml_breakdown.to_dict(),
                "team_fit": self.team_fit_breakdown.to_dict(),
                "trend": self.trend_breakdown.to_dict(),
            },
            "context": {
                "school_name": self.school_name,
                "school_division": self.school_division,
                "player_position": self.player_position,
            },
            "interpretation": self.interpretation,
        }

    def to_summary_dict(self) -> Dict[str, Any]:
        """Condensed output for API responses"""
        return {
            "final_z_score": round(self.final_z_score, 3),
            "percentile": round(self.percentile, 1),
            "bucket": self.bucket,
            "interpretation": self.interpretation,
        }


@dataclass
class PlayerStats:
    """
    Input structure for player statistics.

    All stats are optional to handle missing data gracefully.
    Missing stats will use division average (no impact on z-score).
    """

    # Hitting / Offensive
    exit_velo: Optional[float] = None       # Exit velocity in mph

    # Speed
    sixty_time: Optional[float] = None      # 60-yard dash in seconds

    # Defensive - Position specific
    inf_velo: Optional[float] = None        # Infielder throw velocity (mph)
    of_velo: Optional[float] = None         # Outfielder throw velocity (mph)
    c_velo: Optional[float] = None          # Catcher throw velocity (mph)
    pop_time: Optional[float] = None        # Catcher pop time (seconds)

    # Physical
    height: Optional[float] = None          # Height in inches
    weight: Optional[float] = None          # Weight in lbs

    # Position
    primary_position: str = "IF"            # IF, OF, C, etc.

    def get_position_velo(self) -> Optional[float]:
        """Get the relevant position velocity based on primary position"""
        position_upper = self.primary_position.upper()

        if position_upper in ["C", "CATCHER"]:
            return self.c_velo
        elif position_upper in ["OF", "OUTFIELD", "OUTFIELDER", "LF", "CF", "RF"]:
            return self.of_velo
        else:
            # Default to infielder (IF, 1B, 2B, 3B, SS, etc.)
            return self.inf_velo

    def is_catcher(self) -> bool:
        """Check if player is a catcher"""
        return self.primary_position.upper() in ["C", "CATCHER"]


@dataclass
class MLPredictions:
    """
    Input structure for ML prediction outputs.
    """
    d1_probability: float               # Probability of D1 level (0-1)
    p4_probability: Optional[float]     # Probability of P4 level if D1 (0-1)
    is_elite: bool = False              # Elite P4 flag
    d1_prediction: bool = False         # Binary D1 prediction
    p4_prediction: bool = False         # Binary P4 prediction
    confidence: str = "Medium"          # High, Medium, Low


@dataclass
class SchoolData:
    """
    Input structure for school/program data.
    """
    school_name: str
    division: int                       # 1, 2, 3
    conference: Optional[str] = None    # For D1: P4 conference name or None
    is_power_4: bool = False            # True if P4 conference
    division_percentile: float = 50.0   # 0-100 percentile within division

    # Massey ratings (lower = better)
    offensive_rating: Optional[float] = None
    defensive_rating: Optional[float] = None

    # Trend data
    trend: str = "stable"               # "improving", "stable", "declining"
    trend_change: Optional[float] = None  # Rating change over years
    trend_years: Optional[str] = None   # e.g., "2023-2025"

    def get_division_group(self) -> str:
        """Get the division group string for benchmark lookup"""
        if self.division == 1:
            return "P4" if self.is_power_4 else "Non-P4 D1"
        elif self.division == 2:
            return "D2"
        elif self.division == 3:
            return "D3"
        else:
            return "NAIA"  # Default for other divisions