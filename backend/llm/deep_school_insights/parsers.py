"""Deterministic roster + stats HTML parsing and player/stat matching.

Pure Python — no network, no LLM. All functions here take in-memory soup or
already-parsed lists and return dataclasses from ``types``.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Comment

from backend.roster_scraper.roster_parser import normalize_class_year, normalize_position
from backend.roster_scraper.sidearm_scraper import SidearmRosterScraper

from .types import MatchedPlayer, ParsedPlayer, ParsedStatLine


OFFICIAL_SOURCE_TYPES = {
    "official_roster",
    "official_stats",
    "official_news",
    "official_signing",
    "official_schedule",
    "official_bio",
    "official_conference",
    "official_ncaa",
}
DEFAULT_TRUSTED_DOMAINS = {
    "ncaa.com",
    "www.ncaa.com",
    "stats.ncaa.org",
    "perfectgame.org",
    "www.perfectgame.org",
    "prepbaseball.com",
    "www.prepbaseball.com",
    "prepbaseballreport.com",
    "www.prepbaseballreport.com",
}

_COLLEGE_KEYWORDS = re.compile(
    r"\b(university|college|community\s+college|cc|jc|juco|institute)\b",
    re.IGNORECASE,
)


def _looks_like_college(name: str) -> bool:
    return bool(_COLLEGE_KEYWORDS.search(name))


_NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def _normalize_name_parts(name: str) -> Tuple[str, str]:
    """Return (first, last) from either 'First Last' or 'Last, First' format.

    Trailing generational suffixes (Jr, Sr, II, III, IV) are rolled into the
    last-name half. Roster pages typically render names as ``"Aaron Graves II"``
    while stats pages use ``"Graves II, Aaron"`` — without this normalization
    the rsplit would set last=``"ii"`` on the roster side and last=``"graves ii"``
    on the stats side, and the two would never pair.
    """
    name = re.sub(r"\d+", "", name).strip()
    if "," in name:
        parts = name.split(",", 1)
        return parts[1].strip().lower(), parts[0].strip().lower()
    tokens = name.split()
    suffix_parts: List[str] = []
    while tokens and tokens[-1].lower().rstrip(".") in _NAME_SUFFIXES:
        suffix_parts.insert(0, tokens.pop().rstrip(".").lower())
    if len(tokens) >= 2:
        first = " ".join(tokens[:-1]).strip().lower()
        last = " ".join([tokens[-1].lower(), *suffix_parts]).strip()
        return first, last
    if len(tokens) == 1:
        last = " ".join([tokens[0].lower(), *suffix_parts]).strip()
        return "", last
    # Fallback when the name was pure suffix or empty after stripping digits.
    return "", " ".join(suffix_parts) or name.strip().lower()


def _normalize_domain(url: str) -> str:
    if not url:
        return ""
    domain = urlparse(url).netloc.strip().lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def _trusted_domains_for_school(school: Dict[str, Any]) -> List[str]:
    domains = set(DEFAULT_TRUSTED_DOMAINS)
    for key in (
        "athletics_url",
        "athletics_website",
        "roster_url",
        "school_website",
        "website",
        "school_url",
        "conference_url",
    ):
        value = school.get(key)
        if isinstance(value, str):
            domain = _normalize_domain(value)
            if domain:
                domains.add(domain)
    return sorted(domains)


def _parse_int(value: str) -> int:
    """Parse a string to int, returning 0 on failure."""
    try:
        return int(re.sub(r"[^\d]", "", value.strip()))
    except (ValueError, AttributeError):
        return 0


def clean_soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["script", "style", "nav", "footer", "header", "iframe"]):
        tag.decompose()
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()
    return soup


# ---------------------------------------------------------------------------
# Roster parsing
# ---------------------------------------------------------------------------


def _position_family_from_raw(pos_raw: Optional[str]) -> Optional[str]:
    """Map a raw position string to its family: P, C, OF, or INF.

    Tokenizes on non-alphanumerics so long-form names like
    ``"Right-Handed Pitcher"`` and ``"Left Handed Pitcher"`` are recognized
    as P (otherwise they used to fall through to INF).
    """
    if not pos_raw:
        return None
    cleaned = pos_raw.strip().lower().replace(".", "")
    if "/" in cleaned:
        cleaned = cleaned.split("/")[0].strip()
    tokens = set(re.findall(r"[a-z0-9]+", cleaned))
    if "pitcher" in tokens or tokens & {"rhp", "lhp", "rp", "sp", "p", "closer", "cl"}:
        return "P"
    if "catcher" in tokens or cleaned == "c":
        return "C"
    if tokens & {"of", "lf", "cf", "rf", "outfield", "outfielder"}:
        return "OF"
    if "field" in tokens and tokens & {"left", "center", "right"}:
        return "OF"
    return "INF"


def _parsed_player_quality(player: ParsedPlayer) -> int:
    score = 0
    if player.position_raw:
        score += 2
    if player.position_family:
        score += 2
    if player.position_normalized:
        score += 2
    if player.class_year_raw:
        score += 1
    if player.normalized_class_year is not None:
        score += 2
    if player.previous_school:
        score += 1
    if player.hometown:
        score += 1
    return score


def _parsed_roster_quality(players: Sequence[ParsedPlayer]) -> int:
    return sum(_parsed_player_quality(player) for player in players)


def _build_parsed_players(raw_players: Sequence[Dict[str, Any]]) -> List[ParsedPlayer]:
    parsed: List[ParsedPlayer] = []
    for raw in raw_players:
        name = raw.get("name", "").strip()
        if not name:
            continue

        pos_raw = raw.get("position")
        pos_normalized = normalize_position(pos_raw) if pos_raw else None
        pos_family = _position_family_from_raw(pos_raw) if pos_raw else None

        year_raw = raw.get("class_year")
        year_int, is_redshirt = normalize_class_year(year_raw) if year_raw else (None, False)

        previous_school = raw.get("high_school") or raw.get("previous_school")

        parsed.append(ParsedPlayer(
            name=name,
            jersey_number=raw.get("jersey_number"),
            position_raw=pos_raw,
            position_normalized=pos_normalized,
            position_family=pos_family,
            class_year_raw=year_raw,
            normalized_class_year=year_int,
            is_redshirt=is_redshirt,
            high_school=previous_school if previous_school and not _looks_like_college(previous_school) else None,
            previous_school=previous_school if previous_school and _looks_like_college(previous_school) else None,
            hometown=raw.get("hometown"),
        ))
    return parsed


def _dedupe_parsed_players(players: Sequence[ParsedPlayer]) -> List[ParsedPlayer]:
    deduped: Dict[Tuple[str, str], ParsedPlayer] = {}
    for player in players:
        key = (
            " ".join((player.name or "").strip().lower().split()),
            (player.jersey_number or "").strip().lower(),
        )
        existing = deduped.get(key)
        if existing is None or _parsed_player_quality(player) > _parsed_player_quality(existing):
            deduped[key] = player
    return list(deduped.values())


def parse_roster_players(soup: BeautifulSoup) -> List[ParsedPlayer]:
    """Parse roster HTML into structured player records using the best available layout."""
    scraper = SidearmRosterScraper.__new__(SidearmRosterScraper)
    candidates: List[List[ParsedPlayer]] = []
    for parse_fn in (
        scraper._parse_card_layout,
        scraper._parse_table_layout,
        scraper._parse_generic_table,
    ):
        raw_players = parse_fn(soup)
        if not raw_players:
            continue
        parsed_players = _build_parsed_players(raw_players)
        deduped = _dedupe_parsed_players(parsed_players)
        if deduped:
            candidates.append(deduped)

    if not candidates:
        return []

    return max(candidates, key=lambda players: (_parsed_roster_quality(players), len(players)))


# ---------------------------------------------------------------------------
# Stats parsing
# ---------------------------------------------------------------------------


_NUXT_DATA_RE = re.compile(
    r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>',
    re.DOTALL,
)


def _load_nuxt_data(html: str) -> Optional[List[Any]]:
    """Extract and parse the Nuxt 3 hydration island, returning None if absent."""
    m = _NUXT_DATA_RE.search(html)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, list):
        return None
    return data


def parse_nuxt_roster_players(html: str) -> List[ParsedPlayer]:
    """Extract a roster from a Sidearm Nextgen Nuxt 3 hydration island.

    Nextgen roster pages (Clemson, SDSU, ODU, etc.) render the roster
    client-side, so the legacy Sidearm card/table parsers find nothing.
    The hydration payload carries player records as dicts with snake_case
    keys: ``first_name``, ``last_name``, ``full_name``, ``jersey_number``,
    plus ``player_position_id`` / ``class_level_id`` that resolve to
    numeric IDs (the human-readable position/class labels live on a
    separate API endpoint, not in the page payload).

    We can therefore reliably extract names + jerseys but **not** positions
    or class years from the data island alone. Downstream,
    ``match_players_to_stats`` backfills ``position_family="P"`` from the
    matched pitching stats, so pitchers still get classified end-to-end.

    Returns ``[]`` when no Nuxt data island is present.
    """
    data = _load_nuxt_data(html)
    if data is None:
        return []

    def resolve(value: Any) -> Any:
        if isinstance(value, int) and 0 <= value < len(data):
            return data[value]
        return value

    # Player records have last_name + (first_name OR full_name) AND at least
    # one player-only attribute. Coaches/staff lack these — gate on player
    # attributes to keep them out, since the same dict shape is reused for
    # both populations on most Nextgen sites (e.g. ODU embeds 11 staff
    # records alongside 42 player records).
    _PLAYER_ATTR_KEYS = {
        "jersey_number", "jersey_number_label",
        "height_feet", "height", "weight",
        "class_level_id", "class_year_id",
        "player_position_id", "position_id",
    }
    _STAFF_MARKER_KEYS = {"staff_member_id", "staff_member", "staff", "coach_title_id"}

    seen: set = set()
    players: List[ParsedPlayer] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        keys = set(item.keys())
        if "last_name" not in keys or not keys & {"first_name", "full_name"}:
            continue
        if keys & _STAFF_MARKER_KEYS:
            continue
        if not keys & _PLAYER_ATTR_KEYS:
            continue
        full_name = resolve(item.get("full_name"))
        first = resolve(item.get("first_name"))
        last = resolve(item.get("last_name"))
        if isinstance(full_name, str) and full_name.strip():
            name = full_name.strip()
        elif isinstance(first, str) and isinstance(last, str):
            name = f"{first.strip()} {last.strip()}".strip()
        else:
            continue
        if not name:
            continue

        jersey_raw = resolve(item.get("jersey_number"))
        if jersey_raw is None:
            jersey_raw = resolve(item.get("jersey_number_label"))
        jersey = (
            str(jersey_raw).strip()
            if jersey_raw not in (None, "")
            else None
        )
        key = (name.lower(), jersey or "")
        if key in seen:
            continue
        seen.add(key)

        hometown = resolve(item.get("hometown"))
        high_school = resolve(item.get("high_school"))
        previous_school = resolve(item.get("previous_school"))

        players.append(ParsedPlayer(
            name=name,
            jersey_number=jersey,
            position_raw=None,
            position_normalized=None,
            position_family=None,
            class_year_raw=None,
            normalized_class_year=None,
            is_redshirt=False,
            high_school=high_school if isinstance(high_school, str) else None,
            previous_school=(
                previous_school
                if isinstance(previous_school, str) and _looks_like_college(previous_school)
                else None
            ),
            hometown=hometown if isinstance(hometown, str) else None,
        ))
    return players


def parse_nuxt_stats_records(html: str) -> List[ParsedStatLine]:
    """Extract player stat rows from a Sidearm Nextgen Nuxt 3 hydration island.

    Nextgen sites render stats client-side, so the static HTML has no tables
    for ``parse_stats_records`` to find. The hydration payload at
    ``<script id="__NUXT_DATA__">`` carries the same data as a position-coded
    JSON array: every dict value is either a primitive or an integer index
    into the top-level array (devalue format).

    Pitching rows have an ``inningsPitched`` key; batting rows have
    ``atBats``. Both carry ``playerName`` and ``playerUniform`` (jersey).
    Multiple stat scopes (cumulative, conference, splits) emit duplicates,
    so we dedupe on (name, jersey, stat_type) and keep the first occurrence
    — the cumulative scope appears first in the payload.

    Returns ``[]`` when no Nuxt data island is present, so callers can
    cleanly fall back to the HTML-table parser.
    """
    data = _load_nuxt_data(html)
    if data is None:
        return []

    def resolve(value: Any) -> Any:
        if isinstance(value, int) and 0 <= value < len(data):
            return data[value]
        return value

    records: List[ParsedStatLine] = []
    seen: set = set()
    for item in data:
        if not isinstance(item, dict) or "playerName" not in item:
            continue
        is_pitching = "inningsPitched" in item
        is_batting = ("atBats" in item) and not is_pitching
        if not (is_pitching or is_batting):
            continue
        if resolve(item.get("isAFooterStat")) is True:
            continue
        name = resolve(item.get("playerName"))
        if not isinstance(name, str):
            continue
        name = name.strip()
        if not name or name.lower() == "totals":
            continue
        unif = resolve(item.get("playerUniform"))
        jersey = str(unif) if unif not in (None, "") else None
        gp = _parse_int(resolve(item.get("gamesPlayed")) or "")
        gs = _parse_int(resolve(item.get("gamesStarted")) or "")
        # Pitchers often have GS=0 but heavy appearances; carry that signal
        # via games_played so downstream high-usage logic can use the GP gate.
        if is_pitching and gp == 0:
            gp = _parse_int(resolve(item.get("appearances")) or "")

        stat_type = "pitching" if is_pitching else "batting"
        key = (name, jersey, stat_type)
        if key in seen:
            continue
        seen.add(key)
        records.append(ParsedStatLine(
            jersey_number=jersey,
            player_name=name,
            stat_type=stat_type,
            games_played=gp,
            games_started=gs,
        ))
    return records


def parse_stats_records(soup: BeautifulSoup) -> List[ParsedStatLine]:
    """Parse batting and pitching stats tables into structured records."""
    records: List[ParsedStatLine] = []

    for table in soup.find_all("table"):
        headers_raw = [th.get_text(strip=True) for th in table.find_all("th")[:30]]
        headers_upper = [h.upper() for h in headers_raw]
        rows = table.find_all("tr")
        if len(rows) < 3:
            continue

        h_set = set(headers_upper)
        is_batting = bool(
            {"AVG", "AB"} & h_set
            and not {"ERA", "IP", "W-L", "APP", "APP-GS", "SV"} & h_set
        )
        is_pitching = bool(
            {"ERA", "IP", "W-L", "APP", "APP-GS", "WHIP", "SV"} & h_set
        )
        if not is_batting and not is_pitching:
            continue

        stat_type = "batting" if is_batting else "pitching"

        name_idx = None
        number_idx = None
        gp_idx = None
        gs_idx = None
        for i, h in enumerate(headers_upper):
            if h in {"PLAYER", "NAME"} or (h == "" and i <= 1):
                name_idx = i
            elif h in {"#", "NO", "NO."}:
                number_idx = i
            elif h == "GP" or h == "G":
                gp_idx = i
            elif h == "GS":
                gs_idx = i
            elif h == "GP-GS" or h == "APP-GS":
                gp_idx = i  # combined column, parse below

        if name_idx is None:
            for i, h in enumerate(headers_upper):
                if h not in {"#", "NO", "NO."} and i <= 2:
                    name_idx = i
                    break

        body_rows = table.select("tbody tr") or rows[1:]
        for row in body_rows:
            cell_tags = row.find_all(["td", "th"])
            cells = [td.get_text(" ", strip=True) for td in cell_tags]
            if len(cells) < 3:
                continue

            player_name = ""
            if name_idx is not None and name_idx < len(cells):
                name_link = cell_tags[name_idx].select_one("a")
                player_name = (
                    name_link.get_text(" ", strip=True) if name_link else cells[name_idx]
                )
            if player_name.upper() in {"TOTALS", "TEAM", "OPPONENT", "OPP", "TOTAL", ""}:
                continue

            jersey = cells[number_idx] if number_idx is not None and number_idx < len(cells) else None

            gp = 0
            gs = 0
            if gp_idx is not None and gp_idx < len(cells):
                gp_val = cells[gp_idx]
                if "-" in gp_val:
                    parts = gp_val.split("-")
                    gp = _parse_int(parts[0])
                    gs = _parse_int(parts[1]) if len(parts) > 1 else 0
                else:
                    gp = _parse_int(gp_val)
            if gs_idx is not None and gs_idx < len(cells):
                gs = _parse_int(cells[gs_idx])

            records.append(ParsedStatLine(
                jersey_number=jersey,
                player_name=player_name,
                stat_type=stat_type,
                games_played=gp,
                games_started=gs,
            ))

    return records


# ---------------------------------------------------------------------------
# Player-stats matching
# ---------------------------------------------------------------------------


def match_players_to_stats(
    players: List[ParsedPlayer],
    stats: List[ParsedStatLine],
) -> List[MatchedPlayer]:
    """Cross-reference roster players with stat lines by jersey + last name.

    When the roster page itself doesn't expose a player's position (some older
    Sidearm Classic .aspx sites surface only names + jerseys), the stats page
    becomes the only signal for whether a player is a pitcher. After matching,
    we backfill ``position_family`` / ``position_normalized`` to ``"P"`` for
    any player who has only pitching stats and no roster-derived position —
    otherwise these pitchers would be invisible to the same-family filter in
    ``compute_evidence``.
    """
    import dataclasses

    batting = [s for s in stats if s.stat_type == "batting"]
    pitching = [s for s in stats if s.stat_type == "pitching"]

    def _find_match(player: ParsedPlayer, stat_lines: List[ParsedStatLine]) -> Optional[ParsedStatLine]:
        p_first, p_last = _normalize_name_parts(player.name)
        for stat in stat_lines:
            s_first, s_last = _normalize_name_parts(stat.player_name)
            if player.jersey_number and stat.jersey_number:
                if player.jersey_number == stat.jersey_number and p_last == s_last:
                    return stat
            if p_last == s_last and p_first and s_first and p_first[0] == s_first[0]:
                return stat
        return None

    matched: List[MatchedPlayer] = []
    for player in players:
        bat = _find_match(player, batting)
        pitch = _find_match(player, pitching)
        if (
            pitch is not None
            and bat is None
            and player.position_family is None
        ):
            player = dataclasses.replace(
                player,
                position_family="P",
                position_normalized=player.position_normalized or "P",
            )
        matched.append(MatchedPlayer(player=player, batting_stats=bat, pitching_stats=pitch))
    return matched
