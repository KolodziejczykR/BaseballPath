"""Deterministic roster + stats HTML parsing and player/stat matching.

Pure Python — no network, no LLM. All functions here take in-memory soup or
already-parsed lists and return dataclasses from ``types``.
"""

from __future__ import annotations

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


def _normalize_name_parts(name: str) -> Tuple[str, str]:
    """Return (first, last) from either 'First Last' or 'Last, First' format."""
    name = re.sub(r"\d+", "", name).strip()
    if "," in name:
        parts = name.split(",", 1)
        return parts[1].strip().lower(), parts[0].strip().lower()
    parts = name.rsplit(None, 1)
    if len(parts) == 2:
        return parts[0].strip().lower(), parts[1].strip().lower()
    return "", name.strip().lower()


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
    """Map a raw position string to its family: P, C, OF, or INF."""
    if not pos_raw:
        return None
    cleaned = pos_raw.strip().lower().replace(".", "")
    if "/" in cleaned:
        cleaned = cleaned.split("/")[0].strip()
    if cleaned in {"p", "rhp", "lhp", "rp", "sp", "pitcher", "closer", "cl"}:
        return "P"
    if cleaned in {"c", "catcher"}:
        return "C"
    if cleaned in {"of", "lf", "cf", "rf", "outfield", "outfielder",
                    "left field", "left fielder", "center field",
                    "center fielder", "right field", "right fielder"}:
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
    """Cross-reference roster players with stat lines by jersey + last name."""
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
        matched.append(MatchedPlayer(player=player, batting_stats=bat, pitching_stats=pitch))
    return matched
