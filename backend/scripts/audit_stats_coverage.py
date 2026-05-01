"""Audit how often roster/stats scraping yields usable data per school.

For each sampled school in ``school_data_general``:
  1. Fetch + parse the roster page (`baseball_roster_url`).
  2. Fetch + parse the stats page (URL is `roster_url.replace('/roster','/stats')`).
  3. Compare the count of pitchers found on the roster vs. pitching stat rows.

Reports:
  * Per-school result rows (school, roster size, roster pitchers, stat rows by
    type, pitcher-coverage ratio).
  * Summary: success rates for roster, batting stats, pitching stats; and
    distribution of pitching coverage ratio for the schools where both sides
    have data.

A "healthy" pitcher-stats fetch should yield a pitching-stat row count
roughly equal to the roster pitcher count (some walk-ons missing, some
two-way players double-counted — typically 0.7×–1.2× of the roster count).

Usage::

    python -m backend.scripts.audit_stats_coverage --limit 100 --concurrency 8
    python -m backend.scripts.audit_stats_coverage --limit 50 --region Midwest
    python -m backend.scripts.audit_stats_coverage --school "Ohio State University-Main Campus"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from dataclasses import dataclass
from typing import List, Optional

from dotenv import load_dotenv
from supabase import create_client

# Silence the noisy [TIMING] info logs from fetch.py
logging.basicConfig(level=logging.WARNING)

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.llm.deep_school_insights import (  # noqa: E402
    fetch_and_parse_roster,
    fetch_and_parse_stats,
    match_players_to_stats,
)


@dataclass
class SchoolResult:
    school_name: str
    region: Optional[str]
    roster_url: str
    roster_ok: bool
    roster_n: int
    roster_pitchers: int
    roster_hitters: int  # roster_n − roster_pitchers (post-match)
    stats_total: int
    stats_batting: int
    stats_pitching: int
    matched_pitching: int
    matched_batting: int
    error: Optional[str] = None

    @property
    def pitching_ratio(self) -> Optional[float]:
        """matched_pitching / roster_pitchers — the actionable pitcher coverage.

        Raw `stats_pitching` is inflated because Sidearm pages typically render
        2–4 pitching tables (cumulative, game log, vs LHP/RHP, situational)
        and the parser counts them all. The matcher dedupes via jersey+lastname,
        so `matched_pitching` is the true count of unique pitchers with data.
        """
        if self.roster_pitchers == 0:
            return None
        return self.matched_pitching / self.roster_pitchers

    @property
    def batting_ratio(self) -> Optional[float]:
        """matched_batting / roster_hitters — coverage of position players.

        Hitters per roster are derived as roster_n − roster_pitchers because
        the stats-based position fallback in `match_players_to_stats` only
        flips pitchers to "P"; non-pitchers remain whatever the roster said
        (or None on Classic .aspx sites). Two-way players are rare enough
        that they don't materially distort the denominator.
        """
        if self.roster_hitters == 0:
            return None
        return self.matched_batting / self.roster_hitters


async def _audit_one(school_row: dict, sem: asyncio.Semaphore) -> SchoolResult:
    name = school_row["school_name"]
    region = school_row.get("region")
    roster_url = school_row["baseball_roster_url"]

    async with sem:
        try:
            school = {"school_name": name, "roster_url": roster_url}
            players, _ = await fetch_and_parse_roster(school)
            stats = await fetch_and_parse_stats(school)
        except Exception as exc:  # pragma: no cover — fetch errors fail the row, not the run
            return SchoolResult(
                school_name=name,
                region=region,
                roster_url=roster_url,
                roster_ok=False,
                roster_n=0,
                roster_pitchers=0,
                roster_hitters=0,
                stats_total=0,
                stats_batting=0,
                stats_pitching=0,
                matched_pitching=0,
                matched_batting=0,
                error=f"{exc.__class__.__name__}: {exc}",
            )

    n_batting = sum(1 for s in stats if s.stat_type == "batting")
    n_pitching = sum(1 for s in stats if s.stat_type == "pitching")

    # Pitcher counts are computed post-match because match_players_to_stats
    # backfills position_family from pitching stats for older Sidearm Classic
    # rosters that don't expose positions on the page itself.
    roster_pitchers = 0
    roster_hitters = 0
    matched_pitching = 0
    matched_batting = 0
    if players:
        matched = match_players_to_stats(players, stats) if stats else []
        if stats:
            roster_pitchers = sum(1 for m in matched if m.player.position_family == "P")
            roster_hitters = len(matched) - roster_pitchers
            matched_pitching = sum(
                1 for m in matched if m.player.position_family == "P" and m.pitching_stats
            )
            matched_batting = sum(
                1 for m in matched if m.player.position_family != "P" and m.batting_stats
            )
        else:
            roster_pitchers = sum(1 for p in players if p.position_family == "P")
            roster_hitters = len(players) - roster_pitchers

    return SchoolResult(
        school_name=name,
        region=region,
        roster_url=roster_url,
        roster_ok=bool(players),
        roster_n=len(players),
        roster_pitchers=roster_pitchers,
        roster_hitters=roster_hitters,
        stats_total=len(stats),
        stats_batting=n_batting,
        stats_pitching=n_pitching,
        matched_pitching=matched_pitching,
        matched_batting=matched_batting,
    )


def _select_schools(args) -> List[dict]:
    load_dotenv()
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

    q = sb.table("school_data_general").select(
        "school_name,baseball_roster_url,region"
    ).not_.is_("baseball_roster_url", "null")

    if args.region:
        q = q.eq("region", args.region)
    if args.school:
        q = q.eq("school_name", args.school)
    if args.limit and not args.school:
        q = q.limit(args.limit)

    rows = q.execute().data or []
    if args.shuffle and not args.school:
        import random
        random.seed(args.seed)
        random.shuffle(rows)
        if args.limit:
            rows = rows[: args.limit]
    return rows


def _print_row(r: SchoolResult) -> None:
    pit_r = r.pitching_ratio
    bat_r = r.batting_ratio
    pit_s = f"{pit_r:>4.2f}" if pit_r is not None else " n/a"
    bat_s = f"{bat_r:>4.2f}" if bat_r is not None else " n/a"
    err = f" ERR={r.error}" if r.error else ""
    print(
        f"{r.school_name[:38]:38s} {(r.region or '?')[:9]:9s} "
        f"roster={r.roster_n:>3d}(P={r.roster_pitchers:>2d}/H={r.roster_hitters:>2d}) "
        f"raw: b={r.stats_batting:>3d} p={r.stats_pitching:>3d}  "
        f"pit:{r.matched_pitching:>3d}/{pit_s}  bat:{r.matched_batting:>3d}/{bat_s}{err}"
    )


def _summarize(results: List[SchoolResult]) -> None:
    n = len(results)
    if n == 0:
        print("\nNo results.")
        return

    roster_ok = sum(1 for r in results if r.roster_ok)
    bat_ok = sum(1 for r in results if r.stats_batting > 0)
    pit_ok = sum(1 for r in results if r.stats_pitching > 0)
    pit_ok_when_pitchers = sum(
        1 for r in results if r.roster_pitchers > 0 and r.stats_pitching > 0
    )
    bat_ok_when_hitters = sum(
        1 for r in results if r.roster_hitters > 0 and r.stats_batting > 0
    )
    have_pitchers = sum(1 for r in results if r.roster_pitchers > 0)
    have_hitters = sum(1 for r in results if r.roster_hitters > 0)

    pit_ratios = [r.pitching_ratio for r in results if r.pitching_ratio is not None]
    bat_ratios = [r.batting_ratio for r in results if r.batting_ratio is not None]

    def _band_counts(ratios):
        healthy = sum(1 for x in ratios if 0.6 <= x <= 1.1)
        too_few = sum(1 for x in ratios if 0 < x < 0.6)
        zero = sum(1 for x in ratios if x == 0)
        return healthy, too_few, zero

    def pct(num, denom):
        return f"{num}/{denom} ({100 * num / denom:.1f}%)" if denom else f"{num}/0"

    def _print_ratio_block(label: str, ratios: List[float]) -> None:
        if not ratios:
            return
        ratios_sorted = sorted(ratios)
        n_r = len(ratios_sorted)
        median = ratios_sorted[n_r // 2]
        healthy, too_few, zero = _band_counts(ratios_sorted)
        print()
        print(f"{label}, n={n_r}:")
        print(f"  median:                             {median:.2f}")
        print(f"  healthy band (0.60–1.10):           {pct(healthy, n_r)}")
        print(f"  too-few (0 < ratio < 0.60):         {pct(too_few, n_r)}")
        print(f"  zero  (no stats matched):           {pct(zero, n_r)}")

    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"Schools audited:                      {n}")
    print(f"Roster fetch (≥1 player):             {pct(roster_ok, n)}")
    print(f"Batting stats fetch (≥1 row):         {pct(bat_ok, n)}")
    print(f"Pitching stats fetch (≥1 row):        {pct(pit_ok, n)}")
    print(
        f"Pitching stats present when roster has pitchers: "
        f"{pct(pit_ok_when_pitchers, have_pitchers)}"
    )
    print(
        f"Batting stats present when roster has hitters:   "
        f"{pct(bat_ok_when_hitters, have_hitters)}"
    )

    _print_ratio_block(
        "Pitching coverage ratio (matched_pitching / roster_pitchers)",
        pit_ratios,
    )
    _print_ratio_block(
        "Batting  coverage ratio (matched_batting  / roster_hitters)",
        bat_ratios,
    )

    errors = [r for r in results if r.error]
    if errors:
        print(f"\nFetch errors: {len(errors)}")
        for r in errors[:10]:
            print(f"  {r.school_name}: {r.error}")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100, help="max schools to audit")
    parser.add_argument("--concurrency", type=int, default=8, help="parallel fetches")
    parser.add_argument("--region", type=str, default=None, help="filter by region")
    parser.add_argument("--school", type=str, default=None, help="audit a single school")
    parser.add_argument("--shuffle", action="store_true", help="random sample")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    schools = _select_schools(args)
    if not schools:
        print("No schools matched filters.")
        return

    print(f"Auditing {len(schools)} schools (concurrency={args.concurrency})...\n")
    print(
        f"{'SCHOOL':42s} {'REGION':9s} "
        f"{'ROSTER':16s} {'STATS':28s} {'COV':14s}"
    )
    print("-" * 110)

    sem = asyncio.Semaphore(args.concurrency)
    t0 = time.monotonic()
    tasks = [_audit_one(row, sem) for row in schools]
    results: List[SchoolResult] = []
    for coro in asyncio.as_completed(tasks):
        r = await coro
        results.append(r)
        _print_row(r)

    print(f"\nElapsed: {time.monotonic() - t0:.1f}s")
    _summarize(results)


if __name__ == "__main__":
    asyncio.run(main())
