"""HTTP fetch + orchestration for roster/stats pages.

Each fetch helper manages its own httpx client lifecycle via ``make_httpx_client``.
``gather_evidence`` is the top-level helper that runs roster+stats fetches
concurrently and feeds the results into ``compute_evidence``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

import httpx

from .evidence import _empty_evidence, compute_evidence
from .parsers import (
    clean_soup,
    match_players_to_stats,
    parse_roster_players,
    parse_stats_records,
)
from .types import GatheredEvidence, ParsedPlayer, ParsedStatLine


logger = logging.getLogger(__name__)


def make_httpx_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(20.0, connect=10.0),
        follow_redirects=True,
        max_redirects=5,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
    )


async def fetch_and_parse_roster(
    school: Dict[str, Any],
) -> Tuple[List[ParsedPlayer], Optional[str]]:
    """Fetch roster page and parse into structured player records.

    Returns (players, roster_url).  On failure returns ([], roster_url).
    Raises ValueError if roster_url is missing.
    """
    roster_url = school.get("roster_url")
    if not roster_url:
        raise ValueError(
            f"Missing roster_url for {school.get('school_name', 'Unknown')}. "
            "Every school must have a full roster URL in the database."
        )

    school_name = school.get("display_school_name") or school.get("school_name") or "Unknown"
    try:
        async with make_httpx_client() as client:
            resp = await client.get(roster_url)
            resp.raise_for_status()
    except Exception as exc:
        logger.info("Roster page fetch failed for %s (%s): %s", school_name, roster_url, exc)
        return [], roster_url

    soup = clean_soup(resp.text)
    players = parse_roster_players(soup)
    logger.info(
        "Parsed %d players from roster for %s (%s)", len(players), school_name, roster_url,
    )
    return players, roster_url


async def fetch_and_parse_stats(school: Dict[str, Any]) -> List[ParsedStatLine]:
    """Fetch stats page and parse into structured stat records.

    Derives stats URL by replacing /roster with /stats.
    Returns empty list if stats are unavailable.
    Retries once after a delay for JS-heavy sites.
    """
    roster_url = school.get("roster_url", "")
    if not roster_url or "/roster" not in roster_url.lower():
        return []

    stats_url = roster_url.replace("/roster", "/stats")
    school_name = school.get("display_school_name") or school.get("school_name") or "Unknown"

    async with make_httpx_client() as client:
        for attempt in range(2):
            try:
                resp = await client.get(stats_url)
                if resp.status_code == 404:
                    logger.info("Stats page 404 for %s, skipping", school_name)
                    return []
                resp.raise_for_status()
            except Exception as exc:
                if attempt == 0:
                    logger.info(
                        "Stats fetch attempt 1 failed for %s (%s): %s — retrying in 10s",
                        school_name, stats_url, exc,
                    )
                    await asyncio.sleep(10.0)
                    continue
                logger.info("Stats fetch failed for %s after retry: %s", school_name, exc)
                return []

            soup = clean_soup(resp.text)
            records = parse_stats_records(soup)

            if records:
                logger.info(
                    "Parsed %d stat lines for %s from %s",
                    len(records), school_name, stats_url,
                )
                return records

            if attempt == 0:
                logger.info(
                    "Stats page for %s had no stat tables on attempt 1 — retrying in 10s",
                    school_name,
                )
                await asyncio.sleep(10.0)
                continue

            logger.info("Stats page for %s had no usable stat tables after retry", school_name)
            return []

    return []


async def gather_evidence(
    school: Dict[str, Any],
    player_stats: Dict[str, Any],
    trusted_domains: Sequence[str],
) -> GatheredEvidence:
    """Gather evidence deterministically: fetch, parse, match, compute."""
    school_name = school.get("display_school_name") or school.get("school_name") or "Unknown School"

    roster_coro = fetch_and_parse_roster(school)
    stats_coro = fetch_and_parse_stats(school)
    (players, roster_url), stats = await asyncio.gather(roster_coro, stats_coro)

    if not players:
        logger.info("No players parsed for %s — returning empty evidence", school_name)
        return _empty_evidence(f"Could not parse roster for {school_name}.")

    matched = match_players_to_stats(players, stats)

    evidence = compute_evidence(
        matched_players=matched,
        player_stats=player_stats,
        roster_url=roster_url or "",
        stats_available=bool(stats),
    )

    logger.info(
        "Computed evidence for %s: %d players, %d same-family, %d departures, stats=%s",
        school_name,
        len(players),
        evidence.roster_context.same_family_count or 0,
        evidence.roster_context.likely_departures_same_family or 0,
        "yes" if stats else "no",
    )
    return evidence
