"""
Run the full backend recommendation pipeline end-to-end with LLM reasoning.

This script:
1) Builds a sample request payload
2) Calls the preferences filtering endpoint function directly
3) Queues LLM reasoning (if enabled) and polls for results

Requirements:
- SUPABASE_URL and SUPABASE_SERVICE_KEY in environment
- OPENAI_API_KEY in environment (when use_llm_reasoning=True)
- Celery worker + Redis running for LLM queue
"""

import asyncio
import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.api.routers.preferences import filter_schools_by_preferences, get_llm_reasoning


def _sample_request(use_llm_reasoning: bool = True):
    return {
        "user_preferences": {
            "user_state": "CA",
            "preferred_states": ["CA", "AZ"],
            "preferred_regions": ["West"],
            "preferred_school_size": ["Medium", "Large"],
            "max_budget": 45000,
            "min_academic_rating": "B+",
            "min_athletics_rating": "B",
            "min_student_satisfaction_rating": "B",
            "party_scene_preference": ["Moderate"],
            "sat": 1250,
            "act": 28,
            "hs_graduation_year": 2026,
            "must_have_preferences": ["max_budget", "preferred_states", "min_academic_rating"]
        },
        "player_info": {
            "height": 72,
            "weight": 180,
            "primary_position": "SS",
            "exit_velo_max": 90.0,
            "sixty_time": 6.9,
            "inf_velo": 83.0,
            "throwing_hand": "R",
            "hitting_handedness": "R",
            "region": "West"
        },
        "ml_results": {
            "d1_results": {
                "d1_probability": 0.68,
                "d1_prediction": True,
                "confidence": "High",
                "model_version": "v2.1"
            },
            "p4_results": {
                "p4_probability": 0.22,
                "p4_prediction": False,
                "confidence": "Medium",
                "is_elite": False,
                "model_version": "v1.3"
            }
        },
        "limit": 25,
        "sort_by": "playing_time_score",
        "sort_order": "desc",
        "use_llm_reasoning": use_llm_reasoning
    }


async def run():
    payload = _sample_request(use_llm_reasoning=True)
    result = await filter_schools_by_preferences(payload)
    schools = result.get("schools", [])
    print(f"✅ Received {len(schools)} schools")
    print("Recommendation summary:", result.get("recommendation_summary"))

    summary = result.get("recommendation_summary") or {}
    job_id = summary.get("llm_job_id")
    if not job_id:
        print("ℹ️ No LLM job queued.")
        return

    print(f"⏳ Waiting for LLM reasoning job: {job_id}")
    for _ in range(30):
        reasoning_result = await get_llm_reasoning(job_id)
        status = reasoning_result.get("status")
        if status == "completed":
            print("\n✅ LLM reasoning completed\n")
            print("=== Schools ===")
            reasoning = reasoning_result.get("reasoning", {}) or {}
            for idx, school in enumerate(schools, start=1):
                name = school.get("school_name")
                print(f"\n[{idx}] {name}")
                print(f"Division: {school.get('division_group')}")
                print(f"Location: {school.get('location')}")
                print(f"Size: {school.get('size')}")
                print(f"Academics: {school.get('academics')}")
                print(f"Athletics: {school.get('athletics')}")
                print(f"Student Life: {school.get('student_life')}")
                print(f"Financial: {school.get('financial')}")
                print(f"Overall Grade: {school.get('overall_grade')}")
                print(f"Playing Time: {school.get('playing_time')}")
                print(f"Scores: {school.get('scores')}")
                print(f"Pros: {school.get('match_analysis', {}).get('pros')}")
                print(f"Cons: {school.get('match_analysis', {}).get('cons')}")
                if name in reasoning:
                    print("LLM Summary:", reasoning[name].get("summary"))
                    print("LLM Fit Qualities:", reasoning[name].get("fit_qualities"))
                    print("LLM Cautions:", reasoning[name].get("cautions"))
                else:
                    print("LLM Summary: (not available)")

            print("\n=== Inputs ===")
            print("User preferences:", payload.get("user_preferences"))
            print("Player info:", payload.get("player_info"))
            print("ML results:", payload.get("ml_results"))
            return
        if status == "failed":
            print("❌ LLM reasoning failed")
            return
        await asyncio.sleep(2)
    print("⏳ LLM reasoning still in progress")


if __name__ == "__main__":
    asyncio.run(run())
