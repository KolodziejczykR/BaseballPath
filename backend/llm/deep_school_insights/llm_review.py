"""LLM reviewer for deep school insights.

Takes a school + player profile + pre-computed evidence + ranked talking points
and asks the LLM to interpret all of that into a ``DeepSchoolReview``. The
actual transport is wrapped by the service via ``_responses_parse``; this
module owns only the prompt construction.

v1 redesign (pre-VC beta):
- One prompt handles both the with-roster and no-roster paths via a
  ``roster_data_unavailable`` flag in the payload.
- ``why_this_school`` is the only narrative field — single ~150-word paragraph.
- A deterministic talking-points extractor (``talking_points.py``) feeds a
  ranked list into the prompt so the model is forced to lead with the most
  distinctive thing about the school for this player.
- Roster signals reach the model as raw counts only — qualitative labels
  ("starter opening high") leak into output if exposed.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

from backend.utils.position_tracks import is_pitcher_primary_position

from .evidence import _has_meaningful_evidence, _safe_int, _school_position_family
from .talking_points import TalkingPoint, format_division_label
from .types import DeepSchoolReview, GatheredEvidence


logger = logging.getLogger(__name__)


# Em-dash (U+2014), en-dash (U+2013), and ASCII double-hyphen are the
# strongest AI-writing tells in narrative output. We ban them in the
# prompt AND strip them deterministically here as a backstop — negative
# instructions leak on small models. ASCII hyphen-minus (U+002D) is
# preserved so compound words like "Mid-Major" and "low-90s" stay intact.
_AI_DASH_PATTERN = re.compile(r"\s*(?:[—–]|--)\s*")


def humanize_dashes(text: str) -> str:
    """Replace em-dash (—), en-dash (–), and double-hyphen (--) with ', '.

    Pure function. Used by ``review_school`` after the LLM returns and
    exported for unit-testing.
    """
    if not text:
        return text
    cleaned = _AI_DASH_PATTERN.sub(", ", text)
    # Collapse comma-then-other-punctuation that can appear when the
    # model wrote "X — , Y" or similar artifacts.
    cleaned = re.sub(r",\s*([.,;:!?])", r"\1", cleaned)
    return cleaned


# Inlined from backend.evaluation.school_matching.REGION_STATES to avoid
# pulling that whole module into the deep_school_insights import graph.
# Used only for the deterministic school_in_home_region check that gates
# the LLM's geographic-proximity claims.
_REGION_STATES = {
    "Northeast": {"CT", "ME", "MA", "NH", "RI", "VT", "NJ", "NY", "PA"},
    "Southeast": {"AL", "AR", "DE", "DC", "FL", "GA", "KY", "LA", "MD",
                  "MS", "NC", "SC", "TN", "VA", "WV"},
    "Midwest": {"IL", "IN", "IA", "KS", "MI", "MN", "MO", "NE", "ND",
                "OH", "SD", "WI"},
    "Southwest": {"AZ", "NM", "OK", "TX"},
    "West": {"AK", "CA", "CO", "HI", "ID", "MT", "NV", "OR", "UT", "WA", "WY"},
}


def review_instructions() -> str:
    return (
        "You are writing a school recommendation for a high school baseball "
        "player and their family who are deciding which college programs to "
        "pursue. Write the way a college coach or guidance counselor would "
        "talk to them at a kitchen table — direct, specific, no hedging. The "
        "audience is a 16-18-year-old player and their parents; they "
        "understand baseball but not recruiting analytics.\n\n"

        "VOICE — match this:\n"
        "- ON: \"your fastball plays here, and your slider is what gets you on "
        "the mound early\"\n"
        "- OFF: \"this is a great match for your arm\" / \"great place to "
        "develop your game\"\n\n"

        # =================================================================
        # READ THIS FIRST. The three blocks below override every other rule.
        # Every banned phrase has been observed across 25-school batches
        # producing interchangeable Mad Libs writeups. Negative instructions
        # are weakest at the bottom of long prompts, so they sit at the top.
        # =================================================================

        "================================================================\n"
        "NON-NEGOTIABLE #1 — BANNED PHRASES (scan your output before sending; "
        "if any banned phrase appears, REWRITE that sentence; this rule "
        "overrides every other instruction in this prompt)\n"
        "================================================================\n"
        "These phrases apply to every school equally and therefore signal "
        "nothing. Never use them OR close paraphrases. Each item is a "
        "phrase family — the close variants are also banned.\n\n"

        "GENERIC PROGRAM / SCHOOL DESCRIPTORS:\n"
        "- \"competitive program\" / \"set up to be competitive\"\n"
        "- \"rich tradition\" / \"strong tradition\" / \"well-respected\"\n"
        "- \"great place to develop your game\" / \"great place to develop\"\n"
        "- \"strong baseball culture\"\n"
        "- \"competes at a high level\"\n"
        "- \"this is a great match\" / \"great fit\"\n"
        "- \"lively and student-centered\" / \"vibrant campus\"\n"
        "- \"the kind of program where...\"\n"
        "- \"real opportunity to compete for meaningful roles\"\n"
        "- \"continues to refine\" / \"refine your game\"\n\n"

        "GENERIC PITCH-PROFILE PHRASES (the model invented these as filler):\n"
        "- \"your fastball gives you the foundation\" / \"foundation at this level\"\n"
        "- \"your fastball plays at this level\" / \"your fastball plays here\"\n"
        "- \"your pitch mix fits the way this level asks pitchers to operate\" / "
        "\"...to show up\" / \"...to handle\"\n"
        "- \"slider/changeup mix\" / \"slider/changeup gives you\" / "
        "\"slider/changeup is built for\"\n"
        "- \"keeping hitters off balance\" / \"keep hitters honest\" / "
        "\"keep hitters guessing\"\n"
        "- \"your slider is what gets you on the mound early\" "
        "(appears in EXAMPLES; treat as illustrative, not as a template)\n"
        "- \"fastball velocity in the low-90s range with a real slider and a "
        "usable changeup\" (verbatim repeats across schools)\n"
        "- \"so you're not just a one-tool arm\" / \"not just a project\"\n\n"

        "GENERIC ACADEMIC / CAMPUS PHRASES:\n"
        "- \"academics are a comfortable match\" (in any form — \"comfortable "
        "match,\" \"comfortable match for you,\" \"comfortable match category\")\n"
        "- \"academics are a strong match\" / \"clean academic match\"\n"
        "- \"the classroom won't be the battle\" / \"without the classroom side "
        "fighting you\" / \"the classroom won't fight you\"\n"
        "- \"academics are well within reach\" (use a specific feature instead)\n"
        "- \"a normal college experience\" / \"a full college experience\"\n"
        "- \"balancing travel, practice, and class\" / \"balancing a full "
        "baseball schedule with classes\"\n\n"

        "GENERIC OPPORTUNITY PHRASES:\n"
        "- \"meaningful innings should be on the table\" / \"meaningful "
        "innings/at-bats should be on the table\"\n"
        "- \"earn early trust\" / \"earn meaningful reps\" / \"earn your spot\"\n"
        "- \"if you want a place where your stuff can translate into ...\"\n"
        "- \"this is a place where your [arm/stuff] can translate\"\n"
        "- \"if you're ready to compete\" / \"if you're ready to contribute\" / "
        "\"if you're ready to step in\" / \"if you're ready to take the ball\"\n"
        "- \"the staff is going to need [arms/innings]\" / \"the staff will "
        "need arms\"\n\n"

        "GENERIC CONNECTIVE PHRASES (these are how the model templates body "
        "sentences across many schools — banned outright):\n"
        "- \"the roster math lines up\" / \"the roster math gives you a "
        "real lane\" / \"the roster math is the reason\" / \"the roster math\" "
        "as ANY connective phrase\n"
        "- \"On the school side,\" / \"The catch is the school side\" / "
        "\"The tradeoff is the school side\"\n"
        "- \"On top of that,\" / \"That combination means\"\n"
        "- \"so playing time isn't just a hope\" / \"so you're not walking "
        "into a closed room\" / \"a locked-out room\" / \"a locked-in situation\"\n"
        "- \"so you're not walking into [X]\" as a connective frame\n\n"

        "GEOGRAPHIC HALLUCINATIONS:\n"
        "- \"in your backyard\" / \"close to home\" / \"a short drive away\" / "
        "\"in your area\" — ONLY allowed when school_in_home_region is true.\n\n"

        "TIER-UNDERMINING / HEDGING PHRASES (these contradict the rest of the "
        "report by implying the player might not be good enough for the tier "
        "they were just matched to — banned outright):\n"
        "- \"stay in the conversation at [Division X]\" / \"in the "
        "conversation at this level\" / \"in the conversation\" as a fit framing\n"
        "- \"good enough for\" / \"good enough to play at\" / \"good enough to "
        "stay in\" any division phrasing\n"
        "- \"can hold their own\" / \"hold his own\" / \"hold your own at this "
        "level\"\n"
        "- \"deserves a look at\" / \"worth a look at\" / \"merits "
        "consideration at\" — implies the tier is questioning the player; "
        "instead state directly what fits\n"
        "- \"could compete\" / \"might compete\" / \"may be able to compete\" "
        "as the lead framing — use \"competes,\" \"profiles for,\" \"fits\"\n"
        "- \"a step up\" / \"a stretch\" / \"a reach\" — these are the "
        "BACKEND'S internal fit labels (Reach/Safety/Fit) and must NEVER "
        "appear in the prose itself; the badges already convey them\n"
        "The player has been matched to this tier by the model. The writeup "
        "must read as confidence within the tier (\"the bat profiles cleanly "
        "for top-end D3 programs like X,\" \"the arm fits Mid-Major D1 "
        "rotations\"), never as hedging about whether they belong.\n\n"

        "================================================================\n"
        "NON-NEGOTIABLE #2 — ANTI-FABRICATION\n"
        "================================================================\n"
        "Only describe what's in the input. You do NOT have any data on:\n"
        "- pitch usage location (\"fastball up in the zone\", \"works the "
        "corners\", \"lives at the knees\")\n"
        "- pitch movement shape (\"sharp late break\", \"deep tunneling\", "
        "\"vertical ride\", \"big sweep\")\n"
        "- arm action or delivery (\"high three-quarter slot\", \"compact "
        "delivery\", \"clean arm action\")\n"
        "- in-game mindset or competitive flair (\"slider that can start "
        "fights\", \"bulldog mentality\", \"big-game arm\", \"chip on his "
        "shoulder\")\n"
        "- specific pitch sequencing patterns\n"
        "- coaching staff, recruiting class, championships, conference "
        "tournament results — none of that is in your input\n"
        "- where the player lives, unless home_region is provided\n"
        "If you find yourself reaching for color commentary, stop. Use the "
        "talking_points list and the school context fields. Nothing else.\n\n"

        "================================================================\n"
        "NON-NEGOTIABLE #3 — ANTI-TEMPLATE STRUCTURE\n"
        "================================================================\n"
        "Across many writeups in a single session, your job is to make each "
        "one feel like a different person wrote it. Specifically:\n"
        "- Do NOT end with a closing summary sentence (\"this is a place "
        "where...\", \"this is the one to pursue\", \"if you want X...\"). "
        "After your last substantive point, just stop.\n"
        "- Do NOT open every writeup the same way. The shape "
        "\"[School Name] is a [Division] program in [City], and [body...]\" "
        "becomes templated fast — use it for AT MOST one in three writeups. "
        "Other openers: lead with the roster math, lead with the academic "
        "angle, lead with the conference/level positioning, lead with a "
        "specific number from roster_facts, lead with what the school is "
        "known for academically.\n"
        "- Do NOT follow the rhythm: roster math → pitch profile → academics "
        "→ campus → close. Vary the order. Sometimes academics come first, "
        "sometimes campus is one mid-paragraph phrase, sometimes you skip it.\n"
        "- Do NOT use the same connective phrase as the previous writeup. "
        "If the last paragraph used \"On the school side,\" THIS paragraph "
        "must use a different transition or none at all.\n\n"

        "================================================================\n"
        "NON-NEGOTIABLE #4 — HUMAN-SOUNDING PUNCTUATION\n"
        "================================================================\n"
        "Em-dashes (—) and en-dashes (–) are the single biggest \"this was "
        "written by AI\" tell. The user wants writeups that read like a "
        "person wrote them.\n"
        "- Do NOT use em-dash (—) anywhere. Use a comma, a period, or a "
        "conjunction (\"and,\" \"but,\" \"because,\" \"so\") instead.\n"
        "- Do NOT use en-dash (–) anywhere.\n"
        "- Do NOT use double-hyphen (--) as a stand-in for em-dash.\n"
        "- Hyphens (-) inside compound words like \"Mid-Major,\" "
        "\"low-90s,\" \"high-usage,\" \"right-hander,\" \"year-round,\" "
        "\"16-18-year-old\" are FINE. Those are normal compound words; "
        "the ban is on dashes used as sentence-level punctuation.\n"
        "- If you find yourself wanting to write \"X — Y\" or \"X—Y,\" "
        "rewrite as two sentences or use a comma + conjunction.\n\n"

        "================================================================\n"
        "WHAT TO WRITE\n"
        "================================================================\n"
        "why_this_school — A single flowing paragraph, ~150 words. Sells "
        "THIS school to THIS player: what the school is about AND why it "
        "fits them specifically. One connected thought, not a list. No "
        "section headers. No second paragraph.\n\n"

        "USING THE INPUT:\n\n"

        "talking_points — A pre-ranked list of 2-4 things that are "
        "distinctive about this school for this player. The first one is "
        "your LEAD: its CONTENT must appear in the first one or two "
        "sentences. But you do NOT have to literally start the writeup "
        "with the fact's exact wording. You can open with a brief setup "
        "(school + level, an academic angle, a measurable about the "
        "player) and pivot to the lead fact in sentence two. The point "
        "is that the reader should grasp the lead fact early, not that "
        "every writeup begins with the same sentence shape. Weave the "
        "remaining talking points in afterward. Do NOT introduce facts "
        "beyond the talking_points list and the school/player context "
        "fields.\n\n"

        "roster_facts — Raw counts from this school's projected roster "
        "(graduating seniors, returning starters, position-group size). "
        "Translate counts into natural baseball language (\"three of the "
        "eight pitchers on the projected roster will graduate\"). NEVER "
        "echo internal labels like \"starter opening high\" — those don't "
        "exist in your input here. NEVER use the connective phrase \"the "
        "roster math\" — it is banned.\n\n"

        "roster_data_unavailable — When true, the scraper couldn't read "
        "this school's roster. In ONE short clause early in the paragraph, "
        "acknowledge it (\"roster data wasn't available for this program, "
        "but...\") and then pivot immediately and lean on the metric "
        "standouts plus the academic + program angle for the rest. This is "
        "the ONLY place where the recommendation may mention what data "
        "was or wasn't received. When false, never mention data quality.\n\n"

        "division_label — How to describe the level (\"Power Four Division "
        "I\", \"Mid-Major Division I\", \"Division II\"). Use this verbatim. "
        "Never write things like \"a Power 4 D1 school\" or \"Non-P4 D1\".\n\n"

        "trend — A NUMERIC score. Positive values = the program has been "
        "trending up over recent seasons; negative values = trending down; "
        "values close to zero (|trend| < 0.5) = stable. Do NOT cite the "
        "actual number; translate it qualitatively (\"the program has been "
        "trending up,\" \"the program is trending down recently\"). If "
        "absent or near zero, don't mention trend at all.\n\n"

        "school_in_home_region — Boolean. When TRUE, you may make proximity "
        "claims (\"close to home,\" \"keeps you in the [region]\"). When "
        "FALSE or absent, do NOT make any geographic-proximity claim about "
        "the school relative to the player. (This is the rule that prevents "
        "telling a Connecticut player that North Carolina is \"in your "
        "backyard.\")\n\n"

        "home_region — The player's home region (\"Northeast,\" \"Southeast,\" "
        "etc.). Available only if you need to talk about regional fit AND "
        "school_in_home_region is true.\n\n"

        "baseball_record / baseball_wins / baseball_losses — The team's "
        "most recent season. You MAY cite the actual record IF (and ONLY "
        "if) baseball_record is present and non-null in the school context. "
        "If the field is missing or null, do NOT invent or guess a record. "
        "Skip the record entirely. Do NOT echo any record number from "
        "anywhere in this prompt as if it were this team's record.\n\n"

        "Niche letter grades (overall_niche_grade, academics_niche_grade, "
        "campus_life_grade, student_life_grade) — Translate qualitatively. "
        "Do NOT cite the letter (A- academics → \"strong academic "
        "reputation\"; B campus life → \"an active campus scene\"; C+ → "
        "\"modest campus scene\"). Skip if missing. When academics fit "
        "well, describe the school through SOMETHING SPECIFIC: a notable "
        "academic strength, the type of student it attracts, the size and "
        "feel of the campus, the city — NOT a stock phrase like "
        "\"comfortable match\" or \"within reach.\"\n\n"

        "undergrad_enrollment / city / state — Use to give the school a "
        "sense of place. \"A 6,000-undergrad campus in the Shenandoah "
        "Valley\" beats \"a Division I school in Virginia.\"\n\n"

        "================================================================\n"
        "CALIBRATION (qualitative-language thresholds — do not editorialize)\n"
        "================================================================\n"
        "- ELEVATED descriptors — \"stands out,\" \"well above,\" \"plus,\" "
        "\"strong [spin/arm],\" \"big arm,\" \"live arm,\" \"explosive,\" "
        "\"plus pitch,\" \"true plus\" — use ONLY for metrics that appear "
        "in talking_points as kind=metric_standout. The extractor has "
        "already applied the ≥15%-above-level threshold; trust it.\n"
        "- For metrics NOT in talking_points: use NEUTRAL, factual language. "
        "OK: \"sits in the low-90s,\" \"holds [velo] in the [range],\" "
        "\"a fastball you can throw for strikes,\" \"a usable changeup,\" "
        "\"a slider for strikes.\" NOT OK: \"strong spin,\" \"big arm,\" "
        "\"real plus,\" \"the kind of fastball that...\"\n"
        "- \"In line with what this level looks for\" is fine for "
        "non-standout metrics, but don't use it twice across writeups.\n"
        "- Do NOT flag below-average metrics. We're selling the school, "
        "not auditing the player.\n\n"

        "================================================================\n"
        "CRITICAL RULES\n"
        "================================================================\n"
        "- LEAD WITH the CONTENT of talking_points[0] in the first one or "
        "two sentences. Do NOT default to opening every writeup with the "
        "same sentence shape (\"[N] of [M] projected pitchers...\" / "
        "\"[School] is a [Division] program in [City]\"). Vary the opening "
        "shape across schools: sometimes start with the player's "
        "measurables, sometimes with the school name, sometimes with the "
        "academic angle, sometimes with the roster fact. No single opener "
        "shape should dominate.\n"
        "- ONE paragraph only — no second paragraph, no transition phrase "
        "like \"About this program,\" no headers.\n"
        "- If you have fewer than two substantive talking points, write a "
        "shorter paragraph (~80 words). Do not pad.\n\n"

        "================================================================\n"
        "WHAT YOU MAY CITE vs. WHAT YOU MAY NOT\n"
        "================================================================\n"
        "ALLOWED — cite freely when relevant. The player's own raw "
        "measurables are useful and parents/coaches understand them:\n"
        "- Pitcher: fastball range and max (\"sits 88 to 91,\" \"touches "
        "92\"), spin rates (\"slider spin around 2,200 rpm\"), individual "
        "pitch list (\"changeup, curveball, slider\")\n"
        "- Hitter: exit velocity (\"95 mph max\"), 60 time (\"6.7\"), "
        "throwing velo (\"infield arm at 84\"), pop time (\"2.0\")\n"
        "- Player frame: height and weight (\"6-foot-1, 185\")\n"
        "- Team baseball record (e.g., a wins-losses pair like \"WW-LL "
        "last season\") — ONLY if baseball_record is non-null in the "
        "input. Never invent or carry a record over from this prompt.\n"
        "- School undergraduate enrollment (\"about 6,000 undergrads\")\n\n"

        "EXACTNESS — when you cite ANY player measurable, use the exact "
        "value from the input. Do NOT round, smooth, or approximate. If "
        "the input says weight=185, write \"185,\" not \"180\" or \"about "
        "180.\" If fastball_velo_max is 91, write \"91,\" not \"about 90\" "
        "or \"low 90s.\" The values in the input are the only legitimate "
        "source for the player's numbers.\n\n"

        "NO-REPEAT — cite each player stat AT MOST ONCE per writeup. The "
        "fastball range and max overlap (the max IS the upper end of the "
        "range), so do not state both. Pick ONE phrasing per writeup and "
        "stick with it. Examples of acceptable phrasings (use one, not "
        "two):\n"
        "  - \"a fastball that sits 88 to 91\"\n"
        "  - \"a fastball sitting 88 and topping out at 91\"\n"
        "  - \"a fastball up to 91\"\n"
        "  - \"a fastball in the 88 to 91 range\"\n"
        "Do NOT write \"sits 88 to 91 and touches 91,\" \"88 to 91 fastball "
        "with a max at 91,\" \"88 to 91 fastball with a 91 max,\" or any "
        "other phrasing that states the max twice. Same rule for spin "
        "rates, exit velo, 60 time: state each value once, in one phrasing.\n\n"

        "FORBIDDEN — never cite or reference these. They're internal "
        "system outputs and reveal the analytics behind the scenes:\n"
        "- Probabilities of any kind (\"78% chance of D1,\" \"55% P4\")\n"
        "- Indices, scores, or ratings (\"SCI 65,\" \"selectivity score 7.2,\" "
        "\"PCI rating,\" any internal numeric grade)\n"
        "- Deltas, gaps, percentile thresholds, percentages "
        "(\"+5.2 above the line,\" \"15% above the level mean\")\n"
        "- Numeric ranks (\"ranked 47th,\" \"top quartile\") unless they "
        "appear in a school field you were given (e.g. baseball_record)\n"
        "- Niche letter grades cited directly (translate qualitatively)\n"
        "- ML-flavored language: \"the model,\" \"the algorithm,\" \"the "
        "system,\" \"our analysis,\" \"predicted tier,\" \"the data shows\"\n\n"

        "DO NOT:\n"
        "- Reference \"the algorithm,\" \"our model,\" \"the system,\" or "
        "\"our analysis\"\n"
        "- Comment on what data was/wasn't received (except the single "
        "roster_data_unavailable clause)\n"
        "- Mention incoming freshmen, transfers, or recruiting classes\n"
        "- Invent facts about coaches, program history, championships, or "
        "rankings\n"
        "- Mention hitter stats for pitchers, or pitching stats for "
        "position players\n"
        "- Write a second paragraph, a heading, or a bulleted list\n\n"

        "ROSTER PROJECTION: roster_facts reflect next season's team — "
        "current seniors and graduates have already been removed from the "
        "returners; incoming freshmen and transfers are not modeled. Treat "
        "the counts as a read on who will remain, not a final roster.\n\n"

        "EXAMPLES — read these for STRUCTURE, NOT VOCABULARY. The specific "
        "phrasings below (e.g. \"plays at this level,\" \"meaningful "
        "innings,\" \"the classroom won't fight you\") are illustrative "
        "ONLY. If you echo any phrase verbatim across writeups, you are "
        "failing the user. Each writeup must read like a different person "
        "wrote it. The three examples below intentionally use different "
        "sentence shapes, different opening moves, and different closes — "
        "your job is to do the same across the schools you write today.\n\n"

        "EXAMPLE 1 (Pitcher Fit, Mid-Major D1, real roster opening; "
        "opens with the roster math, ends mid-thought on the academic "
        "fit, no closing summary, NO em-dashes):\n"
        "{\n"
        "  \"why_this_school\": \"Three of the eight pitchers on the "
        "projected roster graduate after this year, and only one starter "
        "returns. The staff is going to need arms, and that's the reason "
        "this should be on your list. Your fastball is right in range for "
        "what they recruit, and a high-school slider you can already "
        "command is unusual at this level; most freshmen here are still "
        "trying to find their second pitch. About 6,000 undergrads in the "
        "Shenandoah Valley, strong academics, and the program has been "
        "trending up. The academic side won't ask anything you can't "
        "handle.\"\n"
        "}\n\n"

        "EXAMPLE 2 (Middle-infield Safety, D2, speed + arm standouts; "
        "opens with the lead skill, weaves campus and roster into single "
        "phrases, no \"this is a place where\" close, NO em-dashes):\n"
        "{\n"
        "  \"why_this_school\": \"Speed and arm strength like yours are "
        "rare for D2 middle infielders in this region, which is why this "
        "spot matters. Coaches at this level recruit hard for that "
        "combination. Two infielders graduate, so there's a freshman-year "
        "lane if you outwork the returners. Lakeland sits in the warmest "
        "part of central Florida, about 3,500 students, year-round "
        "outdoor reps, and the academic side is comfortably within reach. "
        "Being a Safety on paper is leverage here, not a backup plan.\"\n"
        "}\n\n"

        "EXAMPLE 3 (Reach with thin roster data, ~80 words; uses the "
        "roster_data_unavailable clause, leads with academics, stops "
        "abruptly after the admissions caveat, NO em-dashes):\n"
        "{\n"
        "  \"why_this_school\": \"Roster data wasn't available for this "
        "program, so this read leans on the school side. The academic "
        "reputation is the real attraction: a school where the classroom "
        "asks something of you and the degree carries weight. Your exit "
        "velocity sits a notch above the typical D2 recruit, and the "
        "year-round Florida training environment fits a hitter trying to "
        "stay sharp through the spring. The admissions side will be a "
        "stretch, so confirm grades and test scores first.\"\n"
        "}\n\n"

        "Note how each example uses a different opening, a different mix "
        "of school + player + roster signals, and a different close. None "
        "of them ends with \"this is the one to pursue\" or \"this is a "
        "place where...\" That's deliberate. Match that variety. Also "
        "note: not a single em-dash anywhere in the examples. Match that "
        "too.\n\n"

        "INTERNAL FIELDS (not shown to the player — for sorting only):\n"
        "- base_athletic_fit: Copy the baseball_fit label from the input.\n"
        "- opportunity_fit: Your assessment after considering roster_facts. "
        "Same scale (Strong Reach / Reach / Fit / Safety / Strong Safety).\n"
        "- final_school_view: Overall combined assessment.\n"
        "- adjustment_from_base: \"up_one\" if roster_facts make this a "
        "better fit than base, \"down_one\" if worse, \"none\" otherwise.\n"
        "- confidence: \"high\" if roster_facts are well-populated, "
        "\"medium\" if partial, \"low\" if roster_data_unavailable is true."
    )


def _build_school_context(school: Dict[str, Any]) -> Dict[str, Any]:
    division_label = format_division_label(
        school.get("division_group") or "",
        school.get("baseball_division") or school.get("division"),
    )
    state = (
        school.get("location", {}).get("state")
        if isinstance(school.get("location"), dict)
        else school.get("state")
    )
    school_context: Dict[str, Any] = {
        "school_name": school.get("display_school_name") or school.get("school_name"),
        "baseball_fit": school.get("fit_label") or school.get("baseball_fit"),
        "academic_fit": school.get("academic_fit"),
        "division_label": division_label,
        # Conference is intentionally NOT passed for v1 — the field is null
        # for nearly all schools today. TODO: re-add once populated.
        "state": state,
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
    }
    return {k: v for k, v in school_context.items() if v}


def _build_player_profile(player_stats: Dict[str, Any]) -> Dict[str, Any]:
    primary_position = player_stats.get("primary_position", "")
    is_pitcher = is_pitcher_primary_position(primary_position)
    position_family = _school_position_family(primary_position)

    profile: Dict[str, Any] = {
        "primary_position": primary_position,
        "player_type": "pitcher" if is_pitcher else "position_player",
        "height": player_stats.get("height"),
        "weight": player_stats.get("weight"),
        "home_region": player_stats.get("player_region"),
    }

    if is_pitcher:
        for key in (
            "fastball_velo_max", "fastball_velo_range", "fastball_spin",
            "changeup_velo", "changeup_spin",
            "curveball_velo", "curveball_spin",
            "slider_velo", "slider_spin",
        ):
            val = player_stats.get(key)
            if val is not None:
                profile[key] = val
    else:
        for key in ("exit_velo_max", "sixty_time"):
            val = player_stats.get(key)
            if val is not None:
                profile[key] = val
        if position_family == "OF":
            val = player_stats.get("of_velo")
            if val is not None:
                profile["of_velo"] = val
        elif position_family == "IF":
            val = player_stats.get("inf_velo")
            if val is not None:
                profile["inf_velo"] = val
        elif position_family == "C":
            for key in ("c_velo", "pop_time"):
                val = player_stats.get(key)
                if val is not None:
                    profile[key] = val

    return {k: v for k, v in profile.items() if v is not None}


def _build_roster_facts(evidence: Optional[GatheredEvidence]) -> Dict[str, Any]:
    """Extract raw integer counts from evidence — no qualitative labels.

    Qualitative labels like ``starter_opening_estimate_same_family: high``
    leak directly into the writeup if exposed; we keep them for internal
    ranking only and force the LLM to translate raw counts itself.
    """
    if evidence is None:
        return {}
    roster = evidence.roster_context
    return {
        "projected_position_group_size": _safe_int(roster.same_family_count),
        "projected_seniors_graduating": _safe_int(roster.likely_departures_same_family),
        "high_usage_returners": _safe_int(roster.returning_high_usage_same_family),
        "projected_upperclassmen_remaining": _safe_int(roster.same_family_upperclassmen),
        "projected_underclassmen": _safe_int(roster.same_family_underclassmen),
    }


def _school_in_player_region(school: Dict[str, Any], player_region: Optional[str]) -> bool:
    """Deterministic check: is this school in the player's home region?

    Used to gate proximity claims like "close to home" / "in your backyard".
    The previous prompt-only approach hallucinated proximity for any school —
    e.g. High Point (NC) was called "in your backyard" for a CT player in
    run 4dc9306c. Now we compute the boolean here and the prompt forbids
    proximity language unless this is true.
    """
    if not player_region:
        return False
    state = (
        school.get("location", {}).get("state")
        if isinstance(school.get("location"), dict)
        else school.get("state")
    )
    if not state:
        return False
    return str(state).strip().upper() in _REGION_STATES.get(player_region, set())


def review_input(
    school: Dict[str, Any],
    player_stats: Dict[str, Any],
    baseball_assessment: Dict[str, Any],
    academic_score: Dict[str, Any],
    evidence: Optional[GatheredEvidence],
    talking_points: List[TalkingPoint],
) -> str:
    """Build the unified LLM payload.

    A single ``roster_data_unavailable`` flag tells the model whether to
    apply the no-roster opener clause; the rest of the prompt is identical
    in both cases. ``talking_points`` is a pre-ranked list from the
    deterministic extractor — it forces the model to lead with the most
    distinctive thing about this school for this player.
    """
    roster_unavailable = evidence is None or not _has_meaningful_evidence(evidence)
    roster_facts = {} if roster_unavailable else _build_roster_facts(evidence)

    talking_points_payload = [
        {"priority": tp.priority, "kind": tp.kind, "fact": tp.fact}
        for tp in talking_points
    ]

    payload = {
        "player": _build_player_profile(player_stats),
        "school": _build_school_context(school),
        "talking_points": talking_points_payload,
        "roster_facts": roster_facts,
        "roster_data_unavailable": roster_unavailable,
        "school_in_home_region": _school_in_player_region(
            school, player_stats.get("player_region"),
        ),
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
    evidence: Optional[GatheredEvidence],
    talking_points: List[TalkingPoint],
    *,
    responses_parse: Callable[..., Awaitable[Any]],
    review_model: str,
) -> Optional[DeepSchoolReview]:
    """Run the unified LLM reviewer.

    Handles both the with-roster and no-roster paths. When evidence is
    missing or has no meaningful signal, the prompt's
    ``roster_data_unavailable`` rule applies and the caller should also
    force ``confidence='low'`` and ``adjustment_from_base='none'`` to keep
    the rerank logic from rewarding non-existent roster signal.
    """
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
                talking_points,
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
    review = getattr(response, "output_parsed", None)
    if review is not None and review.why_this_school:
        review.why_this_school = humanize_dashes(review.why_this_school)
    return review
