"""
LLM Analysis Module for BaseballPATH
Generates enhanced recruitment insights using OpenAI API
"""

import json
import os
import sys
from typing import Dict, Any, Optional
from openai import OpenAI
from datetime import datetime
from dotenv import load_dotenv

# Add project root to Python path to enable backend imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Load environment variables
load_dotenv()

# Import your existing types
from backend.utils.player_types import PlayerType, PlayerCatcher, PlayerInfielder, PlayerOutfielder
from backend.utils.prediction_types import MLPipelineResults

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def call_openai_api(prompt: str, model: str = "gpt-5") -> Optional[Dict[str, Any]]:
    """
    Call OpenAI API with the generated prompt.
    
    Args:
        prompt: The formatted prompt string
        model: OpenAI model to use (default: gpt-4o-mini for cost efficiency)
        
    Returns:
        Parsed JSON response from LLM or None if error
    """
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system", 
                    "content": "You are an expert college baseball recruitment advisor. Always return valid JSON responses."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            # temperature=0.3,  # Lower temperature for more consistent outputs
            # max_tokens=4000,  # Adjust based on expected response length
            response_format={"type": "json_object"}  # Ensure JSON response
        )
        
        # Parse the JSON response
        content = response.choices[0].message.content
        return json.loads(content)
        
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        print(f"Raw response: {content}")
        return None
        
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return None



def build_recruiting_prompt(
    player: PlayerType, ml_results: MLPipelineResults, graduation_year: str = None, gpa: float = None, playerPreferences: dict | None = None) -> str:
    """
    Construct the LLM prompt for college baseball recruiting recommendations.
    Assumes:
      - player has get_player_type()
      - ml_results has:
          - get_final_prediction() -> str
          - get_player_probabilities() -> Dict[str, Dict[str, float]]
          - get_pipeline_confidence() -> str in {"High", "Medium", "Low"}
    """

    prefs = playerPreferences or {}
    # Get player info using existing method
    player_info_dict = player.get_player_info()
    
    # Format player data for prompt
    player_info = f"""
    PLAYER PROFILE:
    - Position: {player_info_dict.get('primary_position', 'N/A')}
    - Player Type: {player.get_player_type()}
    - Exit Velocity: {player_info_dict.get('exit_velo_max', 'N/A')} mph
    - 60-yard Time: {player_info_dict.get('sixty_time', 'N/A')} seconds
    - Height: {player_info_dict.get('height', 'N/A')} inches
    - Weight: {player_info_dict.get('weight', 'N/A')} lbs
    - Region: {player_info_dict.get('player_region', 'N/A')}
    - Throwing Hand: {player_info_dict.get('throwing_hand', 'N/A')}
    - Hitting Handedness: {player_info_dict.get('hitting_handedness', 'N/A')}
    """

    # Add position-specific velocity
    if isinstance(player, PlayerCatcher):
        player_info += f"\n- Catcher Velocity: {player_info_dict.get('c_velo', 'N/A')} mph"
        player_info += f"\n- Pop Time: {player_info_dict.get('pop_time', 'N/A')} seconds"
    elif isinstance(player, PlayerInfielder):
        player_info += f"\n- Infield Velocity: {player_info_dict.get('inf_velo', 'N/A')} mph"
    elif isinstance(player, PlayerOutfielder):
        player_info += f"\n- Outfield Velocity: {player_info_dict.get('of_velo', 'N/A')} mph"
    
    # Add optional fields
    if graduation_year:
        player_info += f"\n- Graduation Year: {graduation_year}"
    if gpa:
        player_info += f"\n- GPA: {gpa}"

    # ML results block (stringify gracefully)
    model_probs = ml_results.get_player_probabilities()
    model_probs_str = model_probs if isinstance(model_probs, str) else str(model_probs)

    ml_predictions = f"""
    ML PREDICTION RESULTS:
    - Final Classification: {ml_results.get_final_prediction()}
    - Model Probabilities: {model_probs_str}
    - Model Confidence: {ml_results.get_pipeline_confidence()}
    """

    # Player preferences (free-form dict becomes bullet list)
    pref_lines = []
    for k, v in prefs.items():
        pref_lines.append(f"- {k}: {v}")
    preferences_block = "\n".join(pref_lines) if pref_lines else "- (none provided)"

    # The main LLM instruction

    #The 'fitscore' is 0-100, where higher scores mean the athlete is a better fit at the school. The fitscore is calculated as follows:
    prompt = f"""
    You are an expert college BASEBALL recruiting advisor for U.S. college programs. You will give the athlete a list of schools that he will best fit at 
    with his baseball skills (the model prediction) and the user's preferences (the user input). You will then rank the schools based on a 'fitscore'. You
    will assign the fitscore to a school based on how well you think it fits the criteria given (0-100). 

    USER PLAYER'S INFORMATION/STATS:
    {player_info}

    We used a propietary machine learning model to make these predictions, predicting which level of baseball the student can play baseball at in college.
    The model is trained on data from 2017-2023 and can predict with ~75-80% accuracy. The buckets predict what division the player can play at, 
    either Power 4 (SEC, ACC, BIG 12, BIG 10 conferences), Non Power 4 Division 1 (all other D1 conferences), or Non Division 1 (D2, D3, JUCO, NAIA).

    MODEL PREDICTION:
    {ml_predictions}

    PLAYER PREFERENCES (must be respected in recommendations; use to break ties and rank within tier):
    {preferences_block}

    CRITICAL RULES
    1) You MUST return exactly 30 schools in "schoolRecommendations".
    2) Respect the ML pipeline confidence to determine the fraction of schools originating from the model’s predicted group (the “ML Group”):
    - High confidence  → at least 27 of 30 schools (≥90%) from the ML Group
    - Medium confidence → at least 24 of 30 schools (≥80%) from the ML Group
    - Low confidence → at least 21 of 30 schools (≥70%) from the ML Group
    Definition of “ML Group”:
        • If provided in context (ml_results.get_candidate_schools()), treat those as the ML Group.
        • Otherwise infer by the model’s division/level probabilities (e.g., D1/P4 vs non‑P4, D2, D3, JUCO/NAIA) and construct a school pool consistent with the highest‑probability tiers.
    3) WEB LOOKUPS ARE REQUIRED:
    a) For each recommended school:
        - Look up and include the official current baseball roster page URL for the upcoming season (use the athletics site).
        - Look up Niche (niche.com) page for the university and include it.
        - Pull Niche ratings relevant to the user’s preferences (e.g., Academics, Campus Life, Value, Athletics).
    b) Use trustworthy sources only; highly prefer official athletics sites for roster, niche.com for school ratings. If multiple sources are used, include them in a "sources" object.
    4) PLAYING TIME FILTER (HARD CONSTRAINT; DO NOT LIST SCHOOLS THAT FAIL THIS):
    - Evaluate playing time availability at the user's PRIMARY POSITION by inspecting the roster.
    - Consider both COUNT and QUALITY of current players at that position:so
        • Count: number of FR/SO/JR/SR at that position; class years matter (underclassmen block future PT).
        • Quality: basic stat indicators (e.g., GP/GS, BA/OBP/SLG for hitters; IP, ERA, K/BB for pitchers; fielding %/innings for C/SS/IF/OF). If incumbents underperform, the opening may still be favorable.
    - If projected path to meaningful innings/starts is poor (e.g., multiple productive underclassmen at same position), EXCLUDE that school even if it matches otherwise.
    - Explicitly mention playing time rationale in "reasoning".
    5) Preference alignment and realism:
    - Prioritize playerPreferences (intended major, region, school size, urban/suburban/rural vibe, cost sensitivity if provided).
    - Use the ML model’s division/level signal as the core guardrail; only use raw stats for strengths/weaknesses commentary and for roster/position comparisons.
    - Be honest about level (e.g., if model leans D2/D3, only a few stretch D1s are allowed within the “outside” fraction).
    6) FitScore (0–100): combine
    - ML alignment (40%),
    - Playing time outlook (30%),
    - Preference alignment (20%),
    - Program trajectory/competitiveness + Niche-relevant factors (10%).
    Round to integers.
    7) Conferences must be accurate for the school’s current season.
    8) Keep "reasoning" to 2–3 sentences and include BOTH (i) playing time outlook AND (ii) one or two Niche‑relevant notes tied to the player’s preferences.
    9) Sort "schoolRecommendations" by descending fitScore.

    OUTPUT FORMAT — RETURN VALID JSON ONLY (no prose)
    {{
    "profileSummary": "2-3 sentence assessment of player's competitive level and recruiting prospects that references ML confidence.",
    "strengthsAnalysis": ["primary strength 1", "primary strength 2", "primary strength 3"],
    "areasForImprovement": ["area to improve 1", "area to improve 2"],
    "recruitmentStrategy": {{
        "timeline": ["action item with timeline 1", "action item with timeline 2", "action item with timeline 3"],
        "priorities": ["priority 1", "priority 2", "priority 3"],
        "communications": ["communication strategy 1", "communication strategy 2"]
    }},
    "marketAssessment": "Honest 2-3 sentence evaluation of realistic recruiting prospects grounded in ML tier and roster realities.",
    "redFlags": ["concern 1", "concern 2"],
    "quickWins": ["easy improvement 1", "easy improvement 2"],
    "mlGroupAccounting": {{
        "confidence": "<high|medium|low>",
        "minFromMLGroup": 27,  # or 24 or 21 per rule
        "countFromMLGroup": 0, # fill with actual count used
        "definition": "Describe how you defined the ML Group (explicit list present vs inferred by division probabilities)."
    }},
    "schoolRecommendations": [
        {{
        "name": "School Name",
        "location": "City, State",
        "division": "D1|D2|D3|NAIA|JUCO",
        "conference": "Conference Name",
        "fitScore": 0,
        "reasoning": "2-3 sentences covering playing time outlook + Niche factors aligned to preferences.",
        "programSummary": "2-3 sentences about program style/trajectory and how it aligns with player type.",
        "strengths": ["program strength 1","program strength 2"],
        "weaknesses": ["program weakness 1","program weakness 2"],
        "schoolSize": "Small|Medium|Large (and include approx enrollment if available)",
        "rosterCheck": {{
            "position": "{player_info_dict.get('primary_position','N/A')}",
            "upperclassmenAtPosition": <int>,
            "underclassmenAtPosition": <int>,
            "incumbentQualitySummary": "Short note on incumbent performance (stats-based).",
            "playingTimeOutlook": "Favorable|Neutral|Unfavorable"
        }},
        "nicheRatings": {{
            "academics": "grade or score if available",
            "campusLife": "grade/score",
            "athletics": "grade/score",
            "value": "grade/score",
            "notes": "1 short sentence tying a rating to playerPreferences."
        }},
        "sources": {{
            "roster_url": "https://...",
            "niche_url": "https://...",
            "other_urls": ["https://...", "..."]
        }},
        "isFromMLGroup": true
        }}
        // ... exactly 30 total objects, sorted by fitScore desc
    ]
    }}

    STRICT VALIDATION
    - Return JSON only—no markdown, no commentary.
    - Ensure exactly 30 items in schoolRecommendations.
    - Ensure the ML Group count meets the 90/80/70% rule based on model confidence.
    - Do not include any school that fails the playing time filter.
    - Every school must include accurate division, conference, and URLs.
    - If any required source cannot be found or is paywalled, replace the school with another that satisfies all constraints.

    Now think step-by-step. First, determine ML confidence and compute the min required ML Group count. Second, determine/construct the ML Group. Third, web-search and filter by playing time + preferences. Fourth, compute fitScores and rank. Finally, output valid JSON exactly as specified.
    """
    return prompt





def generate_llm_analysis(player: PlayerType, ml_results: MLPipelineResults, graduation_year: str = None, gpa: float = None) -> Optional[Dict[str, Any]]:
    """
    Complete pipeline: Generate prompt and get LLM analysis.
    
    Args:
        player: PlayerType object (PlayerCatcher, PlayerInfielder, or PlayerOutfielder)
        ml_results: MLPipelineResults object from your ML pipeline
        graduation_year: Optional graduation year string
        gpa: Optional GPA float
        
    Returns:
        Complete LLM analysis object or None if error
    """
    # Generate the prompt
    prompt = build_recruiting_prompt(player, ml_results, graduation_year, gpa)
    
    # Get LLM response
    analysis = call_openai_api(prompt)
    
    if analysis:
        # Add metadata
        analysis["generatedAt"] = datetime.now().isoformat()
        analysis["playerHash"] = str(hash(str(player.get_player_info())))
        analysis["playerType"] = player.get_player_type()
        analysis["mlPrediction"] = ml_results.get_final_prediction()
        
    return analysis

# Example usage
if __name__ == "__main__":
    from backend.utils.prediction_types import D1PredictionResult, P4PredictionResult, MLPipelineResults
    
    # Create sample player using your PlayerInfielder class
    sample_player = PlayerInfielder(
        height=72,
        weight=180,
        primary_position="SS",
        hitting_handedness="R",
        throwing_hand="R",
        region="Southeast",
        exit_velo_max=95.0,
        inf_velo=85.0,
        sixty_time=6.8
    )
    
    # Create sample ML results using your classes
    d1_result = D1PredictionResult(
        d1_probability=0.35,
        d1_prediction=False,
        confidence="High",
        model_version="inf_d1_v1.0"
    )
    
    p4_result = P4PredictionResult(
        p4_probability=0.45,
        p4_prediction=False,
        confidence="Medium",
        is_elite=False,
        model_version="inf_p4_v1.0",
        elite_indicators=["High Exit Velocity"]
    )
    
    sample_ml_results = MLPipelineResults(
        player=sample_player,
        d1_results=d1_result,
        p4_results=p4_result
    )

    sample_ml_nond1_results = MLPipelineResults(
        player=sample_player,
        d1_results=d1_result,
        p4_results=None
    )
    
    # Generate analysis
    result = generate_llm_analysis(
        player=sample_player,
        ml_results=sample_ml_nond1_results,
        graduation_year="2026",
        gpa=3.5
    )
    
    if result:
        print("LLM Analysis Generated Successfully!")
        print(json.dumps(result, indent=2))
    else:
        print("Failed to generate LLM analysis")