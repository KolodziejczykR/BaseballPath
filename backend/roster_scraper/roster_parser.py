"""
Roster parsing utilities for BaseballPath
Position normalization, class year normalization, height parsing, redshirt detection
"""

import re
from typing import Optional, Tuple, Dict, List


# ============================================================
# Position normalization
# ============================================================

# Maps raw position strings to normalized positions
POSITION_MAP = {
    # Pitchers
    'p': 'P', 'pitcher': 'P', 'rhp': 'P', 'lhp': 'P',
    'rp': 'P', 'sp': 'P', 'closer': 'P', 'cl': 'P',

    # Catcher
    'c': 'C', 'catcher': 'C',

    # Infield
    '1b': '1B', 'first base': '1B', 'first baseman': '1B',
    '2b': '2B', 'second base': '2B', 'second baseman': '2B',
    'ss': 'SS', 'shortstop': 'SS', 'short stop': 'SS',
    '3b': '3B', 'third base': '3B', 'third baseman': '3B',

    # Outfield
    'lf': 'LF', 'left field': 'LF', 'left fielder': 'LF',
    'cf': 'CF', 'center field': 'CF', 'center fielder': 'CF',
    'rf': 'RF', 'right field': 'RF', 'right fielder': 'RF',

    # DH / Utility
    'dh': 'DH', 'designated hitter': 'DH',
    'utl': 'DH', 'util': 'DH', 'utility': 'DH',
}

# Ambiguous positions that split credit across multiple positions
AMBIGUOUS_POSITIONS = {
    'if': {'1B': 0.25, '2B': 0.25, 'SS': 0.25, '3B': 0.25},
    'inf': {'1B': 0.25, '2B': 0.25, 'SS': 0.25, '3B': 0.25},
    'infield': {'1B': 0.25, '2B': 0.25, 'SS': 0.25, '3B': 0.25},
    'infielder': {'1B': 0.25, '2B': 0.25, 'SS': 0.25, '3B': 0.25},
    'of': {'LF': 0.33, 'CF': 0.34, 'RF': 0.33},
    'outfield': {'LF': 0.33, 'CF': 0.34, 'RF': 0.33},
    'outfielder': {'LF': 0.33, 'CF': 0.34, 'RF': 0.33},
}

# All valid normalized positions
ALL_POSITIONS = ['P', 'C', '1B', '2B', 'SS', '3B', 'LF', 'CF', 'RF', 'DH']


def normalize_position(raw: Optional[str]) -> Optional[str]:
    """
    Normalize a raw position string to a standard position code.
    Returns None for ambiguous positions (IF, OF) — use get_position_credits for those.

    Examples:
        'RHP' -> 'P'
        'Shortstop' -> 'SS'
        'Right-Handed Pitcher' -> 'P'
        'OF' -> None (ambiguous, use get_position_credits)
    """
    if not raw:
        return None

    # Clean: strip whitespace, remove periods, slashes (take first part)
    cleaned = raw.strip().lower().replace('.', '')

    # Handle slash-separated positions like "RHP/1B" — take first
    if '/' in cleaned:
        cleaned = cleaned.split('/')[0].strip()

    if cleaned in AMBIGUOUS_POSITIONS:
        return None

    direct = POSITION_MAP.get(cleaned)
    if direct:
        return direct

    # Long-form fallback: "Right-Handed Pitcher", "Left Handed Pitcher", etc.
    # Tokenize on non-alphanumerics so hyphens and spaces both split.
    tokens = set(re.findall(r'[a-z0-9]+', cleaned))
    if 'pitcher' in tokens or tokens & {'rhp', 'lhp', 'rp', 'sp', 'closer'}:
        return 'P'
    if 'catcher' in tokens:
        return 'C'
    return None


def get_position_credits(raw: Optional[str]) -> Dict[str, float]:
    """
    Get position credits for a raw position string.
    Returns a dict of {position: credit} where credits sum to ~1.0.

    For specific positions: {'P': 1.0}
    For ambiguous: {'LF': 0.33, 'CF': 0.34, 'RF': 0.33}
    For unknown: empty dict

    Examples:
        'RHP' -> {'P': 1.0}
        'OF' -> {'LF': 0.33, 'CF': 0.34, 'RF': 0.33}
        'IF' -> {'1B': 0.25, '2B': 0.25, 'SS': 0.25, '3B': 0.25}
    """
    if not raw:
        return {}

    cleaned = raw.strip().lower().replace('.', '')

    if '/' in cleaned:
        cleaned = cleaned.split('/')[0].strip()

    # Check ambiguous first
    if cleaned in AMBIGUOUS_POSITIONS:
        return AMBIGUOUS_POSITIONS[cleaned].copy()

    # Check direct map
    normalized = POSITION_MAP.get(cleaned)
    if normalized:
        return {normalized: 1.0}

    return {}


# ============================================================
# Class year normalization
# ============================================================

# Redshirt prefix patterns
_REDSHIRT_PATTERN = re.compile(
    r'^(r-|rs\s*|red\s*shirt\s*|redshirt\s*)',
    re.IGNORECASE
)

# Class year map (after stripping redshirt prefix and cleaning)
CLASS_YEAR_MAP = {
    'fr': 1, 'freshman': 1, 'fr.': 1, '1': 1,
    'so': 2, 'sophomore': 2, 'so.': 2, '2': 2,
    'jr': 3, 'junior': 3, 'jr.': 3, '3': 3,
    'sr': 4, 'senior': 4, 'sr.': 4, '4': 4,
    'gr': 5, 'graduate': 5, 'gr.': 5, 'grad': 5, '5': 5,
    'gs': 5, 'grad student': 5,
}


def normalize_class_year(raw: Optional[str]) -> Tuple[Optional[int], bool]:
    """
    Normalize a class year string to (year_number, is_redshirt).

    Args:
        raw: Raw class year string (e.g., 'R-So.', 'Junior', 'Fr.')

    Returns:
        Tuple of (normalized_year 1-5, is_redshirt bool)
        Returns (None, False) if unparseable

    Examples:
        'Fr.' -> (1, False)
        'R-So.' -> (2, True)
        'Senior' -> (4, False)
        'Gr.' -> (5, False)
    """
    if not raw:
        return None, False

    cleaned = raw.strip()

    # Detect redshirt
    is_redshirt = bool(_REDSHIRT_PATTERN.search(cleaned))

    # Strip redshirt prefix for year lookup
    stripped = _REDSHIRT_PATTERN.sub('', cleaned).strip().lower().rstrip('.')

    year = CLASS_YEAR_MAP.get(stripped)
    if year is None:
        # Try with period
        year = CLASS_YEAR_MAP.get(stripped + '.')

    return year, is_redshirt


# ============================================================
# Height parsing
# ============================================================

# Patterns: 6-2, 6'2", 6-02, 6'2, 6' 2", 6-2", 6'02"
_HEIGHT_PATTERN = re.compile(
    r"(\d)'?\s*[-'\s]?\s*(\d{1,2})\"?"
)


def parse_height_inches(raw: Optional[str]) -> Optional[int]:
    """
    Parse a height string into total inches.

    Examples:
        '6-2' -> 74
        "6'2\"" -> 74
        '6-02' -> 74
        '5-11' -> 71
        None -> None
    """
    if not raw:
        return None

    cleaned = raw.strip()
    match = _HEIGHT_PATTERN.search(cleaned)
    if match:
        feet = int(match.group(1))
        inches = int(match.group(2))
        if 4 <= feet <= 7 and 0 <= inches <= 11:
            return feet * 12 + inches

    return None


# ============================================================
# Weight parsing
# ============================================================

_WEIGHT_PATTERN = re.compile(r'(\d{2,3})')


def parse_weight(raw: Optional[str]) -> Optional[int]:
    """
    Parse a weight string into pounds.

    Examples:
        '185' -> 185
        '185 lbs' -> 185
        '185lbs.' -> 185
    """
    if not raw:
        return None

    match = _WEIGHT_PATTERN.search(raw.strip())
    if match:
        weight = int(match.group(1))
        if 100 <= weight <= 350:
            return weight

    return None


# ============================================================
# Bats/throws normalization
# ============================================================

def normalize_hand(raw: Optional[str]) -> Optional[str]:
    """
    Normalize bats/throws value.

    Examples:
        'R' -> 'R', 'Right' -> 'R', 'L' -> 'L', 'S' -> 'S', 'Switch' -> 'S'
    """
    if not raw:
        return None

    cleaned = raw.strip().lower()
    if cleaned in ('r', 'right'):
        return 'R'
    elif cleaned in ('l', 'left'):
        return 'L'
    elif cleaned in ('s', 'switch', 'b', 'both'):
        return 'S'

    return None


# ============================================================
# Full player record normalization
# ============================================================

def normalize_player(raw_data: dict, school_name: str, season: int,
                     division: Optional[int] = None,
                     source_url: Optional[str] = None) -> dict:
    """
    Take raw scraped player data and return a normalized record
    ready for database insertion.

    Args:
        raw_data: Dict with keys like 'name', 'position', 'class_year',
                  'height', 'weight', 'jersey_number', 'hometown',
                  'high_school', 'previous_school', 'bats', 'throws'
        school_name: School name
        season: Season year
        division: NCAA division (1, 2, 3)
        source_url: URL the data was scraped from

    Returns:
        Dict ready for Supabase upsert into roster_players
    """
    from datetime import datetime

    normalized_year, is_redshirt = normalize_class_year(raw_data.get('class_year'))

    return {
        'school_name': school_name,
        'season': season,
        'division': division,
        'player_name': (raw_data.get('name') or '').strip(),
        'jersey_number': (raw_data.get('jersey_number') or '').strip() or None,
        'position': (raw_data.get('position') or '').strip() or None,
        'normalized_position': normalize_position(raw_data.get('position')),
        'class_year': (raw_data.get('class_year') or '').strip() or None,
        'normalized_class_year': normalized_year,
        'is_redshirt': is_redshirt,
        'height_inches': parse_height_inches(raw_data.get('height')),
        'weight_lbs': parse_weight(raw_data.get('weight')),
        'bats': normalize_hand(raw_data.get('bats')),
        'throws': normalize_hand(raw_data.get('throws')),
        'hometown': (raw_data.get('hometown') or '').strip() or None,
        'high_school': (raw_data.get('high_school') or '').strip() or None,
        'previous_school': (raw_data.get('previous_school') or '').strip() or None,
        'source_url': source_url,
        'scraped_at': datetime.now().isoformat(),
    }
