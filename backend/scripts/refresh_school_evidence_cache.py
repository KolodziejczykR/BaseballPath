"""Weekly cron: populate the school_evidence_cache table.

For each school in school_data_general (the canonical universe used by
the live worker), do the same fetch + parse + match the worker does
today, then upsert the position-agnostic MatchedPlayer list into
school_evidence_cache. The worker reads from this table to skip live
fetching during user evaluations.

Usage:
    python -m backend.scripts.refresh_school_evidence_cache
    python -m backend.scripts.refresh_school_evidence_cache --school "Stanford University"
    python -m backend.scripts.refresh_school_evidence_cache --max 10
    python -m backend.scripts.refresh_school_evidence_cache --max 5 --dry-run

Designed to run on Render Cron weekly (e.g. ``0 4 * * 0`` for Sunday
04:00 UTC). Estimated runtime ~70 min for ~300 schools at ~7 s/school
plus the politeness sleep. Exits non-zero if more than 25% of schools
fail — surfaces an at-a-glance signal that something broke wholesale
without burying it in per-school logs.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Allow `python -m backend.scripts.refresh_school_evidence_cache` from
# either the repo root or the backend dir.
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.api.clients.supabase import require_supabase_admin_client
from backend.database.school_evidence_cache import (
    TABLE,
    serialize_matched_players,
)
from backend.llm.deep_school_insights.fetch import (
    fetch_and_parse_roster,
    fetch_and_parse_stats,
)
from backend.llm.deep_school_insights.parsers import match_players_to_stats

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("refresh_school_evidence_cache")

# Politeness: sleep between schools so we don't hammer school websites.
# 5–10 s is in line with school_info_scraper/db_builder/cache_builder_d1.py
# and the Sidearm scraper's anti-bot conventions.
DEFAULT_SLEEP_S = 7.0

# Exit non-zero if the failure rate goes above this — we'd rather a noisy
# alert than a silent partial cache.
MAX_FAILURE_RATIO = 0.25


def _school_names_for_division(division: int) -> set[str]:
    """Resolve --division N → set of school_names via the ranking + mapping tables.

    school_data_general.school_name
        → school_baseball_ranking_name_mapping.team_name
        → baseball_rankings_data.division (int 1/2/3)
    """
    client = require_supabase_admin_client()
    rankings_resp = (
        client.table("baseball_rankings_data")
        .select("team_name")
        .eq("division", division)
        .execute()
    )
    matching_team_names = {
        r["team_name"]
        for r in (rankings_resp.data or [])
        if r.get("team_name")
    }
    if not matching_team_names:
        return set()

    mapping_resp = (
        client.table("school_baseball_ranking_name_mapping")
        .select("school_name, team_name")
        .in_("team_name", list(matching_team_names))
        .execute()
    )
    return {
        r["school_name"]
        for r in (mapping_resp.data or [])
        if r.get("school_name")
    }


def _load_school_universe(
    division: Optional[int], single_school: Optional[str], cap: Optional[int]
) -> List[Dict[str, Any]]:
    """Read the canonical school list from school_data_general.

    Mirrors the source-of-truth used by the live worker via
    ``llm_insight_service.attach_roster_urls`` so the cron sees the same
    roster_url per school the worker would.

    The ``division`` filter is resolved via baseball_rankings_data + the
    name-mapping table (school_data_general itself has no division column).
    """
    client = require_supabase_admin_client()

    division_filter_names: Optional[set[str]] = None
    if division is not None:
        division_filter_names = _school_names_for_division(division)
        if not division_filter_names:
            logger.warning(
                "Division %d resolved to zero schools — nothing to scrape.",
                division,
            )
            return []

    query = client.table("school_data_general").select(
        "school_name, baseball_roster_url"
    )
    if single_school:
        query = query.eq("school_name", single_school)
    elif division_filter_names is not None:
        query = query.in_("school_name", list(division_filter_names))
    resp = query.execute()
    rows = [
        {
            "school_name": r["school_name"],
            "roster_url": r.get("baseball_roster_url"),
        }
        for r in (resp.data or [])
        if r.get("baseball_roster_url")
    ]
    rows.sort(key=lambda r: r["school_name"])
    if cap is not None:
        rows = rows[:cap]
    return rows


async def _refresh_one_school(school: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch + parse + match for one school. Returns an upsert payload.

    Failure modes:
    - Roster fetch fails → source_status='failed'
    - Roster parses but stats fail → source_status='roster_only'
    - Both succeed → source_status='ok'
    """
    school_name = school["school_name"]
    roster_url = school["roster_url"]

    payload: Dict[str, Any] = {
        "school_name": school_name,
        "roster_url": roster_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        # Run roster + stats fetches concurrently per school (same as worker).
        roster_coro = fetch_and_parse_roster(school)
        stats_coro = fetch_and_parse_stats(school)
        (players, _resolved_url), stats = await asyncio.gather(roster_coro, stats_coro)
    except Exception as exc:
        payload["matched_players"] = []
        payload["stats_available"] = False
        payload["source_status"] = "failed"
        payload["error_message"] = f"{type(exc).__name__}: {exc}"[:500]
        return payload

    if not players:
        payload["matched_players"] = []
        payload["stats_available"] = False
        payload["source_status"] = "failed"
        payload["error_message"] = "Roster parse returned 0 players"
        return payload

    matched = match_players_to_stats(players, stats)
    payload["matched_players"] = serialize_matched_players(matched)
    payload["stats_available"] = bool(stats)
    payload["source_status"] = "ok" if stats else "roster_only"
    return payload


def _upsert(payload: Dict[str, Any]) -> None:
    client = require_supabase_admin_client()
    client.table(TABLE).upsert(payload, on_conflict="school_name").execute()


async def _run(
    *,
    division: Optional[int],
    single_school: Optional[str],
    cap: Optional[int],
    sleep_s: float,
    dry_run: bool,
) -> int:
    schools = _load_school_universe(division, single_school, cap)
    if not schools:
        logger.warning("No schools matched the filters — nothing to do.")
        return 0

    logger.info(
        "Refresh starting: %d schools (division=%s single=%s cap=%s dry_run=%s sleep=%.1fs)",
        len(schools), division, single_school, cap, dry_run, sleep_s,
    )

    counts = {"ok": 0, "roster_only": 0, "failed": 0}
    t_start = time.monotonic()

    for i, school in enumerate(schools, start=1):
        t_school_start = time.monotonic()
        try:
            payload = await _refresh_one_school(school)
        except Exception as exc:
            # Defensive: refresh_one_school should never raise (it traps
            # exceptions and returns a 'failed' payload), but if something
            # slips through don't kill the whole run.
            logger.exception(
                "[%d/%d] %s: unhandled exception during refresh: %s",
                i, len(schools), school["school_name"], exc,
            )
            counts["failed"] += 1
            await asyncio.sleep(sleep_s)
            continue

        status = payload["source_status"]
        counts[status] = counts.get(status, 0) + 1
        n_players = len(payload.get("matched_players", []))
        elapsed = time.monotonic() - t_school_start

        if not dry_run:
            try:
                _upsert(payload)
            except Exception as exc:
                logger.warning(
                    "[%d/%d] %s: upsert failed (status=%s, %d players): %s",
                    i, len(schools), school["school_name"], status, n_players, exc,
                )
                counts["failed"] = counts.get("failed", 0) + 1

        logger.info(
            "[%d/%d] %s: status=%s players=%d elapsed=%.2fs",
            i, len(schools), school["school_name"], status, n_players, elapsed,
        )

        # Politeness sleep — skip after the very last school.
        if i < len(schools):
            await asyncio.sleep(sleep_s)

    total_elapsed = time.monotonic() - t_start
    total = sum(counts.values())
    failure_ratio = counts.get("failed", 0) / total if total else 0
    logger.info(
        "Refresh complete: total=%d ok=%d roster_only=%d failed=%d "
        "failure_ratio=%.2f elapsed=%.1fs dry_run=%s",
        total, counts.get("ok", 0), counts.get("roster_only", 0),
        counts.get("failed", 0), failure_ratio, total_elapsed, dry_run,
    )

    if failure_ratio > MAX_FAILURE_RATIO:
        logger.error(
            "FAILURE RATIO %.2f exceeds threshold %.2f — exiting non-zero",
            failure_ratio, MAX_FAILURE_RATIO,
        )
        return 2
    return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument(
        "--school", default=None,
        help="Refresh just this school by exact name (for ad-hoc fixes).",
    )
    p.add_argument(
        "--division", type=int, default=None, choices=[1, 2, 3],
        help="Limit to this NCAA division.",
    )
    p.add_argument(
        "--max", dest="cap", type=int, default=None,
        help="Cap iteration count (for testing / partial runs).",
    )
    p.add_argument(
        "--sleep", type=float, default=DEFAULT_SLEEP_S,
        help=f"Seconds to sleep between schools (default {DEFAULT_SLEEP_S}).",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Fetch + parse but skip the upsert. Useful for verifying scraping works.",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    return asyncio.run(
        _run(
            division=args.division,
            single_school=args.school,
            cap=args.cap,
            sleep_s=args.sleep,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
