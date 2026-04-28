"""Test the balanced (None priority) ranking pipeline across player archetypes.

Runs school matching + cross-school reranking for several test players and prints
a breakdown of the final 25. LLM enrichment is skipped — every school starts
with ranking_adjustment=0.0 and roster_label=unknown — but the deterministic
composite still drives ~90% of the ordering.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.evaluation.academic_scoring import compute_academic_score
from backend.evaluation.competitiveness import effective_tier
from backend.evaluation.school_matching import compute_player_pci, match_and_rank_schools
from backend.llm.deep_school_insights.ranking import (
    _apply_cross_school_reranking,
    _cross_school_sort_key,
    compute_ranking_score,
)
from backend.school_filtering.database.async_queries import AsyncSchoolDataQueries


PROFILES = [
    {
        "label": "P4 player + mid academic",
        "metrics": {
            "height": 73, "weight": 195, "primary_position": "INF", "throwing_hand": "R",
            "exit_velo_max": 99.5, "sixty_time": 6.65, "inf_velo": 90.5,
        },
        "ml": {"final_prediction": "P4 D1", "d1_probability": 0.92, "p4_probability": 0.74},
        "academic": {"gpa": 3.4, "act_score": 25, "sat_score": None, "ap_courses": 2},
    },
    {
        "label": "Non-P4 D1 player + HIGH academic",
        "metrics": {
            "height": 72, "weight": 185, "primary_position": "INF", "throwing_hand": "R",
            "exit_velo_max": 93.0, "sixty_time": 6.95, "inf_velo": 84.0,
        },
        "ml": {"final_prediction": "Non-P4 D1", "d1_probability": 0.78, "p4_probability": 0.18},
        "academic": {"gpa": 3.92, "act_score": None, "sat_score": 1480, "ap_courses": 5},
    },
    {
        "label": "Non-P4 D1 player + LOW academic",
        "metrics": {
            "height": 72, "weight": 185, "primary_position": "INF", "throwing_hand": "R",
            "exit_velo_max": 93.0, "sixty_time": 6.95, "inf_velo": 84.0,
        },
        "ml": {"final_prediction": "Non-P4 D1", "d1_probability": 0.78, "p4_probability": 0.18},
        "academic": {"gpa": 2.7, "act_score": 19, "sat_score": None, "ap_courses": 0},
    },
    {
        "label": "Non-D1 player + HIGH academic",
        "metrics": {
            "height": 71, "weight": 175, "primary_position": "INF", "throwing_hand": "R",
            "exit_velo_max": 86.0, "sixty_time": 7.30, "inf_velo": 78.0,
        },
        "ml": {"final_prediction": "Non-D1", "d1_probability": 0.18, "p4_probability": None},
        "academic": {"gpa": 3.95, "act_score": None, "sat_score": 1500, "ap_courses": 6},
    },
]


def _trim_to_final(schools: List[Dict[str, Any]], final_limit: int = 25) -> List[Dict[str, Any]]:
    """Mirror the trim logic in DeepSchoolInsightService.enrich_and_rerank for None priority."""
    if len(schools) <= final_limit:
        return schools
    MAX_STRONG_SAFETY = 2
    MAX_STRONG_REACH = 2
    MAX_ACAD_STRONG_SAFETY = 5  # balanced (None) cap

    strong_safeties = [s for s in schools if s.get("fit_label") == "Strong Safety"]
    strong_reaches = [s for s in schools if s.get("fit_label") == "Strong Reach"]
    rest = [s for s in schools if s.get("fit_label") not in ("Strong Safety", "Strong Reach")]
    for group in (strong_safeties, strong_reaches, rest):
        group.sort(key=_cross_school_sort_key, reverse=True)
    selected = list(rest)
    selected.extend(strong_safeties[:MAX_STRONG_SAFETY])
    selected.extend(strong_reaches[:MAX_STRONG_REACH])
    selected.sort(key=_cross_school_sort_key, reverse=True)

    acad_ss_count = 0
    acad_capped = []
    for s in selected:
        if (s.get("academic_fit") or "").strip() == "Strong Safety":
            acad_ss_count += 1
            if acad_ss_count <= MAX_ACAD_STRONG_SAFETY:
                acad_capped.append(s)
        else:
            acad_capped.append(s)
    return acad_capped[:final_limit]


def _is_pitcher(position: Optional[str]) -> bool:
    if not position:
        return False
    return position.strip().upper() in {"P", "RHP", "LHP", "SP", "RP", "PITCHER"}


async def run_profile(profile: Dict[str, Any], all_schools: List[Dict[str, Any]]) -> None:
    print()
    print("=" * 130)
    print(f"PROFILE: {profile['label']}")
    print("=" * 130)

    metrics = profile["metrics"]
    ml = profile["ml"]
    acad = profile["academic"]

    is_pitcher = _is_pitcher(metrics.get("primary_position"))
    academic_score = compute_academic_score(
        gpa=acad["gpa"], sat_score=acad.get("sat_score"),
        act_score=acad.get("act_score"), ap_courses=acad["ap_courses"],
    )
    predicted_tier = effective_tier(
        ml["final_prediction"],
        d1_probability=ml.get("d1_probability"),
        p4_probability=ml.get("p4_probability"),
    )
    pci_info = compute_player_pci(
        player_stats=metrics,
        predicted_tier=predicted_tier,
        d1_probability=ml.get("d1_probability"),
        p4_probability=ml.get("p4_probability"),
        is_pitcher=is_pitcher,
    )
    player_pci = float(pci_info.get("player_pci") or 50.0)
    print(
        f"academic effective={academic_score['effective']}  composite={academic_score['composite']}  "
        f"predicted_tier={predicted_tier}  player_pci={player_pci:.2f}  "
        f"within_tier_pct={pci_info.get('within_tier_percentile')}"
    )

    # Stage 1: get the 50-school consideration pool
    consideration = match_and_rank_schools(
        schools=all_schools,
        player_stats=metrics,
        predicted_tier=predicted_tier,
        player_pci=player_pci,
        academic_composite=academic_score["effective"],
        is_pitcher=is_pitcher,
        limit=50,
        consideration_pool=True,
        ranking_priority=None,  # balanced
    )
    print(f"consideration pool size: {len(consideration)}")

    # Stage 2: deterministic ranking_score (no LLM adjustment)
    for s in consideration:
        s["ranking_score"] = compute_ranking_score(float(s.get("delta") or 0.0), 0.0, None)
        s["ranking_adjustment"] = 0.0
        s["research_status"] = "not_requested"
        s["roster_label"] = "unknown"
        s["raw_opportunity_signal"] = None

    # Stage 3: cross-school composite
    _apply_cross_school_reranking(consideration, ranking_priority=None,
                                  player_academic_score=academic_score["effective"])
    consideration.sort(key=_cross_school_sort_key, reverse=True)

    # Stage 4: trim to 25 with the same caps service.py uses
    final = _trim_to_final(consideration, final_limit=25)

    # Breakdown
    fit_counts: Dict[str, int] = {}
    acad_counts: Dict[str, int] = {}
    cross_counts: Dict[str, int] = {}
    for s in final:
        fl = s.get("fit_label", "?")
        al = s.get("academic_fit", "?")
        fit_counts[fl] = fit_counts.get(fl, 0) + 1
        acad_counts[al] = acad_counts.get(al, 0) + 1
        cross_counts[f"{fl}/{al}"] = cross_counts.get(f"{fl}/{al}", 0) + 1

    print(f"\nbaseball_fit counts: {dict(sorted(fit_counts.items()))}")
    print(f"academic_fit counts: {dict(sorted(acad_counts.items()))}")
    print(f"cross-tab (baseball/academic): {dict(sorted(cross_counts.items()))}")
    print()
    print(f"{'#':>3}  {'school':40s}  {'div':18s}  {'bbf':14s}  {'acad':14s}  "
          f"{'d':>6s}  {'ad':>6s}  {'sci':>6s}  {'sel':>4s}  {'comp':>7s}  {'rs':>6s}")
    print("-" * 140)
    for i, s in enumerate(final[:25], 1):
        sel = s.get("academic_selectivity_score")
        sel_str = f"{sel:.1f}" if sel is not None else "  - "
        print(
            f"{i:>3}  {(s.get('school_name') or '')[:40]:40s}  "
            f"{(s.get('division_label') or s.get('division_group') or '')[:18]:18s}  "
            f"{s.get('fit_label', ''):14s}  {s.get('academic_fit', ''):14s}  "
            f"{float(s.get('delta') or 0):>6.2f}  {float(s.get('academic_delta') or 0):>6.2f}  "
            f"{float(s.get('sci') or 0):>6.2f}  {sel_str:>4s}  "
            f"{float(s.get('cross_school_composite') or 0):>7.2f}  "
            f"{float(s.get('ranking_score') or 0):>6.2f}"
        )


async def main() -> None:
    db = AsyncSchoolDataQueries()
    try:
        all_schools = await db.get_all_schools()
    finally:
        await db.close()
    print(f"Loaded {len(all_schools)} schools from database.")

    for profile in PROFILES:
        await run_profile(profile, all_schools)


if __name__ == "__main__":
    asyncio.run(main())
