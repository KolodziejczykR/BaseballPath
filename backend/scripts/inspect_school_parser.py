"""
Manual inspector for deep-school roster/stats parsing and evidence computation.

Examples:
    python3 backend/scripts/inspect_school_parser.py \
        --school "Abilene Christian" \
        --school "Nevada" \
        --position OF

    python3 backend/scripts/inspect_school_parser.py \
        --school "Long Beach State" \
        --position SS \
        --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.api.clients.supabase import get_supabase_admin_client
from backend.llm.deep_school_insights import DeepSchoolInsightService


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect live roster/stats parsing and evidence computation for given schools."
    )
    parser.add_argument(
        "--school",
        action="append",
        dest="schools",
        required=True,
        help="School name. Pass multiple times to inspect multiple schools.",
    )
    parser.add_argument(
        "--position",
        default="OF",
        help="Primary position to use for evidence computation, e.g. OF, SS, P, C.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=5,
        help="How many parsed players/stat lines to print per school.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full inspection output as JSON.",
    )
    return parser.parse_args()


def _load_school_rows(school_names: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    client = get_supabase_admin_client()
    if client is None:
        raise RuntimeError(
            "Supabase admin client is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_KEY."
        )

    response = (
        client.table("school_data_general")
        .select("school_name, baseball_roster_url")
        .in_("school_name", list(school_names))
        .execute()
    )

    rows = response.data or []
    return {str(row.get("school_name") or ""): row for row in rows}


def _player_preview(players: Sequence[Any], sample_size: int) -> List[Dict[str, Any]]:
    preview: List[Dict[str, Any]] = []
    for player in players[:sample_size]:
        preview.append(
            {
                "name": player.name,
                "jersey_number": player.jersey_number,
                "position_raw": player.position_raw,
                "position_family": player.position_family,
                "position_normalized": player.position_normalized,
                "class_year_raw": player.class_year_raw,
                "normalized_class_year": player.normalized_class_year,
                "previous_school": player.previous_school,
            }
        )
    return preview


def _stats_preview(stats: Sequence[Any], sample_size: int) -> List[Dict[str, Any]]:
    preview: List[Dict[str, Any]] = []
    for stat in stats[:sample_size]:
        preview.append(
            {
                "player_name": stat.player_name,
                "jersey_number": stat.jersey_number,
                "stat_type": stat.stat_type,
                "games_played": stat.games_played,
                "games_started": stat.games_started,
            }
        )
    return preview


async def _inspect_school(
    *,
    service: DeepSchoolInsightService,
    school_name: str,
    roster_url: str,
    position: str,
    sample_size: int,
) -> Dict[str, Any]:
    school = {
        "school_name": school_name,
        "display_school_name": school_name,
        "roster_url": roster_url,
    }

    players, resolved_roster_url = await service._fetch_and_parse_roster(school)
    stats = await service._fetch_and_parse_stats(school)

    result: Dict[str, Any] = {
        "school_name": school_name,
        "requested_position": position,
        "roster_url": resolved_roster_url,
        "player_count": len(players),
        "stats_count": len(stats),
        "players_preview": _player_preview(players, sample_size),
        "stats_preview": _stats_preview(stats, sample_size),
    }

    if not players:
        result["error"] = "No players parsed from roster page."
        return result

    matched = service._match_players_to_stats(players, stats)
    evidence = service._compute_evidence(
        matched_players=matched,
        player_stats={"primary_position": position},
        roster_url=resolved_roster_url or "",
        stats_available=bool(stats),
    )
    matched_with_stats = sum(1 for item in matched if item.batting_stats or item.pitching_stats)

    result["matched_player_count"] = len(matched)
    result["matched_with_stats_count"] = matched_with_stats
    result["evidence"] = evidence.model_dump()
    return result


def _print_text_report(result: Dict[str, Any], sample_size: int) -> None:
    print(f"=== {result['school_name']} ===")
    print(f"requested_position: {result['requested_position']}")
    print(f"roster_url: {result.get('roster_url')}")
    print(f"player_count: {result['player_count']}")
    print(f"stats_count: {result['stats_count']}")
    if "matched_player_count" in result:
        print(f"matched_player_count: {result['matched_player_count']}")
        print(f"matched_with_stats_count: {result['matched_with_stats_count']}")

    if result.get("error"):
        print(f"error: {result['error']}")
        print()
        return

    print(f"players_preview (first {sample_size}):")
    for player in result["players_preview"]:
        print(f"  - {player}")

    print(f"stats_preview (first {sample_size}):")
    for stat in result["stats_preview"]:
        print(f"  - {stat}")

    evidence = result["evidence"]
    roster = evidence.get("roster_context") or {}
    recruiting = evidence.get("recruiting_context") or {}
    opportunity = evidence.get("opportunity_context") or {}

    print("evidence_summary:")
    print(f"  roster_context: {roster}")
    print(f"  recruiting_context: {recruiting}")
    print(f"  opportunity_context: {opportunity}")
    print(f"  data_gaps: {evidence.get('data_gaps') or []}")
    print()


async def _run(args: argparse.Namespace) -> List[Dict[str, Any]]:
    rows_by_name = _load_school_rows(args.schools)
    service = DeepSchoolInsightService.__new__(DeepSchoolInsightService)
    results: List[Dict[str, Any]] = []

    for school_name in args.schools:
        row = rows_by_name.get(school_name)
        if row is None:
            results.append(
                {
                    "school_name": school_name,
                    "requested_position": args.position,
                    "error": "School not found in school_data_general.",
                    "player_count": 0,
                    "stats_count": 0,
                    "players_preview": [],
                    "stats_preview": [],
                }
            )
            continue

        roster_url = row.get("baseball_roster_url")
        if not roster_url:
            results.append(
                {
                    "school_name": school_name,
                    "requested_position": args.position,
                    "error": "School found, but baseball_roster_url is missing.",
                    "player_count": 0,
                    "stats_count": 0,
                    "players_preview": [],
                    "stats_preview": [],
                }
            )
            continue

        results.append(
            await _inspect_school(
                service=service,
                school_name=school_name,
                roster_url=str(roster_url),
                position=args.position,
                sample_size=args.sample_size,
            )
        )

    return results


def main() -> int:
    args = _parse_args()
    results = asyncio.run(_run(args))

    if args.json:
        print(json.dumps(results, indent=2))
        return 0

    for result in results:
        _print_text_report(result, args.sample_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
