"""LLM reviewer for deep school insights.

Takes a school + player profile + pre-computed evidence and asks the LLM to
interpret that evidence into a ``DeepSchoolReview``. The actual transport is
wrapped by the service via ``_responses_parse``; this module owns only the
prompt construction.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Awaitable, Callable, Dict, Optional

from backend.utils.position_tracks import is_pitcher_primary_position

from .evidence import _school_position_family
from .types import DeepSchoolReview, GatheredEvidence


# Map raw division_group codes to human-friendly labels
_DIVISION_LABELS = {
    "Power 4 D1": "Division I (Power Conference)",
    "Non-P4 D1": "Division I",
    "Non-D1": "Division II / III / NAIA",
}


logger = logging.getLogger(__name__)


def review_instructions() -> str:
    return (
        "You are writing a school recommendation for a high school baseball player "
        "and their family. They are deciding which college programs to pursue. Your "
        "job is to explain — in plain, conversational English — why this specific "
        "school is worth their attention.\n\n"

        "AUDIENCE: A 16-18 year old player and their parents. They know baseball but "
        "they do not know recruiting analytics. Write the way a knowledgeable family "
        "friend who played college ball would talk to them.\n\n"

        "UNDERSTANDING THE INPUT DATA:\n"
        "The JSON packet contains fields you need to interpret, not repeat:\n"
        "- baseball_fit: How the player's measurables compare to this school's typical "
        "recruits. 'Fit' = well-matched, 'Safety' = player exceeds the school's "
        "level, 'Reach' = school typically recruits stronger athletes, 'Strong Safety' "
        "and 'Strong Reach' are more extreme versions.\n"
        "- academic_fit: Same scale for academics. 'Safety' = player's grades exceed "
        "what the school requires, 'Reach' = the school may be academically challenging "
        "for this player.\n"
        "- metric_comparisons: Each entry has a metric, the player's value, and a "
        "division average. Use these to say things like 'your arm strength is well "
        "above what most programs at this level see' — never cite the raw numbers or "
        "field names.\n"
        "- roster_context: Counts of players at the same position, how many are "
        "upperclassmen likely graduating, and estimated openings. Use this to talk "
        "about opportunity naturally — e.g. 'several upperclassmen on the pitching "
        "staff are set to graduate, which could open the door for you.'\n"
        "- opportunity_context: Summarizes competition and opportunity levels. Use to "
        "gauge whether playing time is realistic.\n"
        "- player_type: Either 'pitcher' or 'position_player'. Only reference metrics "
        "that are relevant to that type. Pitchers have fastball velo, spin rates, and "
        "off-speed pitches. Position players have exit velo, 60-yard dash, and "
        "throwing velo. NEVER mention exit velo, 60 time, or batting metrics for a "
        "pitcher. NEVER mention pitching velocity or spin for a position player.\n"
        "- division_label: A human-friendly description of the school's division level "
        "(e.g. 'Division I' or 'Division II'). Use this when referencing the level, "
        "NOT the raw division_group code.\n"
        "- School info fields: city, undergrad_enrollment, overall_niche_grade, "
        "academics_niche_grade, campus_life_grade, student_life_grade are Niche.com "
        "letter grades (A+, A, B+, etc.) describing the school as a whole. Use these "
        "to paint a picture of campus life and academic quality — do NOT cite the "
        "letter grades directly, translate them (e.g. A- academics = 'strong academic "
        "reputation', C+ campus life = 'modest campus scene').\n"
        "- baseball_record / baseball_wins / baseball_losses: The team's most recent "
        "season record. Use to describe whether the program has been winning recently. "
        "You CAN mention the actual record (e.g. '35-20 last season').\n\n"

        "CRITICAL WRITING RULES:\n"
        "- Write ONLY about what you know. If a field is missing, null, or empty, "
        "skip it. NEVER say 'conference information is not provided' or 'data quality "
        "is mixed' or 'this metric was not included.' The player should never know "
        "what data you did or did not receive. Just write about what you have.\n"
        "- NEVER echo field names or internal labels from the JSON. Do not say "
        "'competition level is described as low' or 'starter opening estimate is "
        "high' or 'position data quality is mixed.' Translate everything into natural "
        "baseball language.\n"
        "- Focus on what makes THIS school different from any other school at the same "
        "level. If the school has a conference, mention it. If it is in a notable "
        "location or state, mention it. If the program is trending up or down, mention "
        "it. Find the unique angle.\n"
        "- Vary your language. Do not start every writeup the same way. Do not use "
        "the same sentence structure across schools.\n\n"

        "WHAT TO WRITE:\n\n"
        "why_this_school — The main writeup. Answer: 'Why should I be excited about "
        "this school?' A single flowing paragraph, roughly 4-6 sentences, ~150 words. "
        "Weave together the strongest reasons: how the player's skills line up, what "
        "is appealing about the program or conference, and any roster opportunity from "
        "graduating players. Make it one connected thought, not a bulleted list "
        "converted to sentences.\n\n"

        "school_snapshot — Help the player picture the school as a place to spend "
        "four years. 2-3 sentences covering: the school itself (enrollment size, "
        "city/location appeal, academic reputation, campus vibe from the grades) AND "
        "the baseball program (recent record if available, conference, program "
        "trajectory). Make it feel like a mini scouting report on the school, not just "
        "the baseball team. Do NOT just restate the division level and state.\n\n"

        "considerations — 0-2 short notes about things genuinely worth knowing for "
        "THIS specific school. These should be substantive and tied to the fit data:\n"
        "  - If academic_fit is 'Strong Safety': note the school may not challenge "
        "them academically\n"
        "  - If academic_fit is 'Reach' or 'Strong Reach': note the school is an "
        "academic stretch and they should confirm their grades/scores are competitive\n"
        "  - If baseball_fit is 'Reach' or 'Strong Reach': note they will need to "
        "outperform expectations to earn playing time\n"
        "  - If the roster is crowded at their position: mention the competition\n"
        "  - If the conference is exceptionally strong: mention the level of "
        "competition\n"
        "Bad examples: generic notes about data quality, missing fields, or anything "
        "that applies to every school. If there is nothing specific to flag, return "
        "an EMPTY list [].\n\n"

        "EXAMPLE — Pitcher looking at a mid-major D1 school that is a fit:\n"
        "{\n"
        '  "why_this_school": "Your arm fits what this program typically looks for '
        "— your fastball plays at this level, and the fact that you already have a "
        "usable slider gives you a second pitch most freshmen at mid-major programs "
        "are still developing. The pitching staff has several upperclassmen who will "
        "be moving on after this season, which means there should be real innings "
        "available for arms that are ready to compete. The program competes in the "
        "Colonial Athletic Association, which is a solid mid-major conference with "
        "good regional exposure. Academically the school is well within your range, "
        'so you can focus on development without the classroom being a constant battle.",\n'
        '  "school_snapshot": "A mid-size university of about 6,000 undergrads in '
        "Harrisonburg, Virginia, known for strong academics and an active campus "
        "scene. The baseball program went 35-20 last season and competes in the CAA, "
        "which has consistently produced regional contenders. The campus is in the "
        'Shenandoah Valley with a classic college-town feel.",\n'
        '  "considerations": [\n'
        '    "The CAA has gotten more competitive in recent years, so earning a '
        'weekend rotation spot will take real performance in the fall."\n'
        "  ]\n"
        "}\n\n"

        "EXAMPLE — Shortstop looking at a D2 safety school:\n"
        "{\n"
        '  "why_this_school": "Your speed and arm strength stand out at this level '
        "— most middle infielders in this conference do not bring that combination. "
        "The program has been trending upward and plays a competitive schedule that "
        "would give you solid exposure. A couple of upperclassmen in the infield are "
        "set to graduate, which opens up a realistic path to playing time as a "
        "freshman. This is the kind of program where your athleticism gives you an "
        'edge from day one.",\n'
        '  "school_snapshot": "A smaller school with about 3,500 students in Lakeland, '
        "Florida, with solid academics and a warm, tight-knit campus community. The "
        "baseball team went 28-18 in the Sunshine State Conference and benefits from "
        'year-round outdoor training weather.",\n'
        '  "considerations": [\n'
        '    "Academically this is a stretch — confirm your test scores are in range '
        'before investing too much time here."\n'
        "  ]\n"
        "}\n\n"

        "DO NOT:\n"
        "- Mention scores, indices, probabilities, deltas, or numeric rankings\n"
        "- Reference 'the algorithm,' 'our model,' 'the system,' or 'our analysis'\n"
        "- Comment on what data was or was not provided / available\n"
        "- Mention incoming freshmen, incoming transfers, or recruiting classes\n"
        "- Invent facts about the school, coaching staff, or program history\n"
        "- Cite raw metric values ('88 mph exit velo') — use relative language "
        "('your bat speed is strong for this level')\n"
        "- Mention hitter stats (exit velo, 60 time) for pitchers or pitching stats "
        "for position players\n\n"

        "ROSTER PROJECTION: roster_evidence reflects next season's team — "
        "current seniors and graduates have been removed. Incoming freshmen "
        "and transfers are not included, so treat openings/competition as a "
        "read on who will remain, not a final roster.\n\n"

        "INTERNAL RANKING FIELDS (not shown to the player — for sorting only):\n"
        "- base_athletic_fit: Copy the baseball_fit label from the input.\n"
        "- opportunity_fit: Your assessment after considering roster evidence. Use the "
        "same scale (Strong Reach / Reach / Fit / Safety / Strong Safety).\n"
        "- final_school_view: Your overall assessment combining athletic and roster fit.\n"
        "- adjustment_from_base: 'up_one' if roster evidence makes this a better fit "
        "than the base label suggests, 'down_one' if worse, 'none' if unchanged.\n"
        "- confidence: 'high' if roster data is solid, 'medium' if partial, 'low' if "
        "thin or unavailable."
    )


def review_input(
    school: Dict[str, Any],
    player_stats: Dict[str, Any],
    baseball_assessment: Dict[str, Any],
    academic_score: Dict[str, Any],
    evidence: GatheredEvidence,
) -> str:
    primary_position = player_stats.get("primary_position", "")
    is_pitcher = is_pitcher_primary_position(primary_position)
    position_family = _school_position_family(primary_position)

    # Translate division_group to a human-friendly label
    raw_division = school.get("division_group") or ""
    division_label = _DIVISION_LABELS.get(raw_division, raw_division)

    school_context: Dict[str, Any] = {
        "school_name": school.get("display_school_name") or school.get("school_name"),
        "baseball_fit": school.get("fit_label") or school.get("baseball_fit"),
        "academic_fit": school.get("academic_fit"),
        "division_label": division_label,
        "conference": school.get("conference"),
        "state": (school.get("location") or {}).get("state") if isinstance(school.get("location"), dict) else school.get("state"),
        "city": school.get("school_city"),
        "undergrad_enrollment": school.get("undergrad_enrollment"),
        "overall_niche_grade": school.get("overall_grade"),
        "academics_niche_grade": school.get("academics_grade"),
        "campus_life_grade": school.get("campus_life_grade"),
        "student_life_grade": school.get("student_life_grade"),
        "baseball_record": school.get("baseball_record"),
        "baseball_wins": school.get("baseball_wins"),
        "baseball_losses": school.get("baseball_losses"),
        "trend": school.get("trend"),
        "metric_comparisons": school.get("metric_comparisons", []),
    }
    # Drop null/empty values so the model doesn't see them
    school_context = {k: v for k, v in school_context.items() if v}

    # Build player profile — only include metrics relevant to player type
    player_profile: Dict[str, Any] = {
        "primary_position": primary_position,
        "player_type": "pitcher" if is_pitcher else "position_player",
        "height": player_stats.get("height"),
        "weight": player_stats.get("weight"),
    }

    if is_pitcher:
        # Pitcher-only metrics
        for key in (
            "fastball_velo_max", "fastball_velo_range", "fastball_spin",
            "changeup_velo", "changeup_spin",
            "curveball_velo", "curveball_spin",
            "slider_velo", "slider_spin",
        ):
            val = player_stats.get(key)
            if val is not None:
                player_profile[key] = val
    else:
        # Position-player-only metrics
        for key in ("exit_velo_max", "sixty_time"):
            val = player_stats.get(key)
            if val is not None:
                player_profile[key] = val
        # Position-specific throwing metrics
        if position_family == "OF":
            val = player_stats.get("of_velo")
            if val is not None:
                player_profile["of_velo"] = val
        elif position_family == "IF":
            val = player_stats.get("inf_velo")
            if val is not None:
                player_profile["inf_velo"] = val
        elif position_family == "C":
            for key in ("c_velo", "pop_time"):
                val = player_stats.get(key)
                if val is not None:
                    player_profile[key] = val

    # Drop null values from player profile
    player_profile = {k: v for k, v in player_profile.items() if v is not None}

    # Build cleaned roster evidence — strip recruiting context and internal
    # field names that the model might parrot
    evidence_dict = evidence.model_dump()
    evidence_dict.pop("recruiting_context", None)
    evidence_dict.pop("data_gaps", None)
    evidence_dict.pop("sources", None)
    # Remove internal quality labels the model tends to echo
    roster_ctx = evidence_dict.get("roster_context") or {}
    roster_ctx.pop("position_data_quality", None)

    payload = {
        "player": player_profile,
        "school": school_context,
        "roster_evidence": evidence_dict,
    }
    return (
        "Write a school fit review for this player using only the provided data.\n"
        f"{json.dumps(payload)}"
    )


async def review_school(
    school: Dict[str, Any],
    player_stats: Dict[str, Any],
    baseball_assessment: Dict[str, Any],
    academic_score: Dict[str, Any],
    evidence: GatheredEvidence,
    *,
    responses_parse: Callable[..., Awaitable[Any]],
    review_model: str,
) -> Optional[DeepSchoolReview]:
    school_name = school.get("display_school_name") or school.get("school_name") or "Unknown School"
    t_start = time.monotonic()
    try:
        response = await responses_parse(
            model=review_model,
            input_text=review_input(
                school,
                player_stats,
                baseball_assessment,
                academic_score,
                evidence,
            ),
            instructions=review_instructions(),
            text_format=DeepSchoolReview,
            max_output_tokens=2500,
        )
    except Exception as exc:
        logger.warning(
            "[TIMING] llm_review school=%r status=failed elapsed=%.2fs err=%s",
            school_name, time.monotonic() - t_start, exc,
        )
        return None
    logger.info(
        "[TIMING] llm_review school=%r status=ok elapsed=%.2fs",
        school_name, time.monotonic() - t_start,
    )
    return getattr(response, "output_parsed", None)
