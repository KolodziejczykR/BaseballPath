"""
Configuration for PBR scraper
"""

import os

# Base URL
PBR_BASE_URL = "https://www.prepbaseballreport.com"

# Class years to scrape
CLASS_YEARS = [2022, 2023, 2024, 2025, 2026, 2027]

# Delays (seconds)
# Conservative defaults for long runs (~53k profiles).
# Can be overridden with --delay flag for testing.
PAGE_LOAD_DELAY = 3.0
BETWEEN_PROFILES_DELAY = 3.0
BETWEEN_PAGES_DELAY = 4.0

# Pagination
COMMITMENTS_PER_PAGE = 100

# Output paths
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "rescraped")
SCHOOL_CACHE_PATH = os.path.join(OUTPUT_DIR, "school_cache.json")
CHECKPOINT_PATH = os.path.join(OUTPUT_DIR, "checkpoint.json")
COMMITMENTS_CSV_PATH = os.path.join(OUTPUT_DIR, "commitments_urls.csv")
ALL_PLAYERS_CSV_PATH = os.path.join(OUTPUT_DIR, "pbr_all_players.csv")

# Stat label -> CSV column name mapping for Best Of stats
STAT_LABEL_MAP = {
    # Pitching - Fastball
    "Velocity (max)": "fastball_velo_max",
    "Velo Range": None,  # context-dependent, handled per-section
    "Spin Rate (avg)": None,  # context-dependent, handled per-section
    # Power
    "Exit Velocity (max)": "exit_velo_max",
    "Exit Velocity (avg)": "exit_velo_avg",
    "Distance (max)": "distance_max",
    "Sweet Spot %": "sweet_spot_p",
    # Hitting
    "Hand Speed (max)": "hand_speed_max",
    "Bat Speed (max)": "bat_speed_max",
    "Rot. Acc (max)": "rot_acc_max",
    "Hard Hit %": "hard_hit_p",
    # Running
    "60-yd": "sixty_time",
    "30-yd": "thirty_time",
    "10-yd": "ten_yard_time",
    "Run speed (max)": "run_speed_max",
    # Defense
    "INF Velo": "inf_velo",
    "OF Velo": "of_velo",
    "C Velo": "c_velo",
    "Pop Time": "pop_time",
}

# Pitch type sections and their column prefixes
PITCH_SECTIONS = {
    "Fastball": "fastball",
    "Changeup": "changeup",
    "Curveball": "curveball",
    "Slider": "slider",
}

# Pitch stat labels -> suffix
PITCH_STAT_SUFFIX = {
    "Velocity (max)": "velo_max",
    "Velo Range": "velo_range",
    "Spin Rate (avg)": "spin",
}

# All stat columns (value + date pairs)
ALL_STAT_COLUMNS = [
    # Pitching
    "fastball_velo_max", "fastball_velo_range", "fastball_spin",
    "changeup_velo_range", "changeup_spin",
    "curveball_velo_range", "curveball_spin",
    "slider_velo_range", "slider_spin",
    # Power
    "exit_velo_max", "exit_velo_avg", "distance_max", "sweet_spot_p",
    # Hitting
    "hand_speed_max", "bat_speed_max", "rot_acc_max", "hard_hit_p",
    # Running
    "sixty_time", "thirty_time", "ten_yard_time", "run_speed_max",
    # Defense
    "inf_velo", "of_velo", "c_velo", "pop_time",
]

# Region mapping (state abbreviation -> region)
STATE_TO_REGION = {
    # Northeast
    "CT": "Northeast", "ME": "Northeast", "MA": "Northeast", "NH": "Northeast",
    "RI": "Northeast", "VT": "Northeast", "NJ": "Northeast", "NY": "Northeast",
    "PA": "Northeast",
    # Midwest
    "IL": "Midwest", "IN": "Midwest", "MI": "Midwest", "OH": "Midwest",
    "WI": "Midwest", "IA": "Midwest", "KS": "Midwest", "MN": "Midwest",
    "MO": "Midwest", "NE": "Midwest", "ND": "Midwest", "SD": "Midwest",
    # South
    "DE": "South", "FL": "South", "GA": "South", "MD": "South",
    "NC": "South", "SC": "South", "VA": "South", "DC": "South",
    "WV": "South", "AL": "South", "KY": "South", "MS": "South",
    "TN": "South", "AR": "South", "LA": "South", "OK": "South",
    "TX": "South",
    # West
    "AZ": "West", "CO": "West", "ID": "West", "MT": "West",
    "NV": "West", "NM": "West", "UT": "West", "WY": "West",
    "AK": "West", "CA": "West", "HI": "West", "OR": "West",
    "WA": "West",
}

# Division classification
def classify_commitment_group(division: str, conference: str) -> str:
    """Classify a school into P4, Non-P4 D1, or Non-D1"""
    if not division:
        return "Unknown"

    division_upper = division.upper().strip()

    # Check for D1 specifically (avoid matching "NCAA II" or "NCAA III")
    is_d1 = any([
        division_upper == "NCAA I",
        division_upper == "NCAA D1",
        division_upper == "D1",
        division_upper == "DIVISION I",
        "NCAA I " in division_upper and "II" not in division_upper,
    ])

    if is_d1:
        # P4 conferences (Power 4 + Notre Dame)
        p4_conferences = {
            "ACC", "Big 12", "Big Ten", "SEC",
            # Common variations
            "Atlantic Coast Conference", "Big 12 Conference",
            "Big Ten Conference", "Southeastern Conference",
        }
        if conference and any(p4 in conference for p4 in p4_conferences):
            return "P4"
        return "Non P4 D1"

    return "Non D1"
