"""
College Selection Pipeline for BaseballPATH V0
Orchestrates the complete college selection process using LLM + data scraping
"""

import json
import os
import sys
from typing import Dict, Any, Optional, List, Tuple
from openai import OpenAI
from datetime import datetime
from dotenv import load_dotenv

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.utils.player_types import PlayerType, PlayerCatcher, PlayerInfielder, PlayerOutfielder
from backend.utils.prediction_types import MLPipelineResults
from backend.utils.preferences_types import UserPreferences
from backend.utils.scraping_types import SchoolInformation
from backend.school_info_scraper.college_scoreboard_retrieval import CollegeScorecardRetriever
from backend.school_info_scraper.niche_bs_scraper import NicheBSScraper
from backend.database.school_data_cache import SchoolDataCache

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class CollegeSelectionPipeline:
    """Complete college selection pipeline orchestrator"""
    
    def __init__(self, delay: float = 2.0):
        """
        Initialize pipeline with scrapers
        
        Args:
            delay: Delay between scraping requests
        """
        self.scorecard_retriever = CollegeScorecardRetriever(delay=delay)
        # Longer delay for Niche scraper to avoid bot detection
        self.niche_scraper = NicheBSScraper(delay=delay * 2.5)
        # Initialize Supabase cache
        try:
            self.cache = SchoolDataCache()
            print("✅ School data cache initialized")
        except Exception as e:
            print(f"⚠️  Cache initialization failed: {e}")
            self.cache = None
    
    def run_complete_pipeline(
        self, 
        player: PlayerType, 
        ml_results: MLPipelineResults, 
        user_preferences: UserPreferences
    ) -> Optional[Dict[str, Any]]:
        """
        Run the complete college selection pipeline
        
        Args:
            player: Player statistics and info
            ml_results: ML prediction results
            user_preferences: User preferences from API
            
        Returns:
            Final analysis with 25 schools or None if error
        """
        print("🏈 Starting College Selection Pipeline...")
        
        # Stage 1: Generate 50 schools with reasoning
        print("\n📝 Stage 1: Generating initial 50 schools...")
        school_list = self._generate_initial_schools(player, ml_results, user_preferences)
        
        if not school_list:
            print("❌ Failed to generate initial school list")
            return None
        
        print(f"✅ Generated {len(school_list)} schools")
        
        # Stage 2: Scrape data for all schools
        print("\n🔍 Stage 2: Scraping data for all schools...")
        school_data = self._scrape_school_data(school_list)
        
        if not school_data:
            print("❌ Failed to scrape school data")
            return None
        
        print(f"✅ Scraped data for {len(school_data)} schools")
        
        # Stage 3: Final LLM selection with all data
        print("\n🎯 Stage 3: Final selection of 25 schools...")
        final_analysis = self._generate_final_selection(
            player, ml_results, user_preferences, school_data
        )
        
        if not final_analysis:
            print("❌ Failed to generate final analysis")
            return None
        
        print("✅ Pipeline completed successfully!")
        return final_analysis
    
    def _generate_initial_schools(
        self,
        player: PlayerType,
        ml_results: MLPipelineResults,
        user_preferences: UserPreferences
    ) -> Optional[List[Tuple[str, str]]]:
        """
        Stage 1: Generate 50 schools using LLM (based on your existing prompt structure)
        
        Returns:
            List of (school_name, city_state) tuples or None if error
        """
        prompt = self._build_initial_generation_prompt(player, ml_results, user_preferences)
        
        try:
            response = client.chat.completions.create(
                model="gpt-5",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert college baseball recruitment advisor. Think deeply about school fit but return only the requested list format."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
            )
            
            # Parse the response to extract school list
            content = response.choices[0].message.content.strip()
            return self._parse_school_list(content)
            
        except Exception as e:
            print(f"Error in initial school generation: {e}")
            return None
    
    def _build_initial_generation_prompt(
        self,
        player: PlayerType,
        ml_results: MLPipelineResults,
        user_preferences: UserPreferences
    ) -> str:
        """Build Stage 1 prompt based on your existing structure"""
        
        # Get player info using existing method
        player_info_dict = player.get_player_info()
        
        # Format player data (reusing your structure)
        player_info = f"""
        PLAYER PROFILE:
        - Position: {player_info_dict.get('primary_position')}
        - Player Type: {player.get_player_type()}
        - Exit Velocity: {player_info_dict.get('exit_velo_max')} mph
        - 60-yard Time: {player_info_dict.get('sixty_time')} seconds
        - Height: {player_info_dict.get('height')} inches
        - Weight: {player_info_dict.get('weight')} lbs
        - Region: {player_info_dict.get('player_region')}
        - Throwing Hand: {player_info_dict.get('throwing_hand')}
        - Hitting Handedness: {player_info_dict.get('hitting_handedness')}
        """
        
        # Add position-specific velocity (from your code)
        if isinstance(player, PlayerCatcher):
            player_info += f"\n- Catcher Velocity: {player_info_dict.get('c_velo', 'N/A')} mph"
            player_info += f"\n- Pop Time: {player_info_dict.get('pop_time', 'N/A')} seconds"
        elif isinstance(player, PlayerInfielder):
            player_info += f"\n- Infield Velocity: {player_info_dict.get('inf_velo', 'N/A')} mph"
        elif isinstance(player, PlayerOutfielder):
            player_info += f"\n- Outfield Velocity: {player_info_dict.get('of_velo', 'N/A')} mph"
        
        # Add optional fields from user preferences
        if user_preferences.hs_graduation_year:
            player_info += f"\n- Graduation Year: {user_preferences.hs_graduation_year}"
        
        # ML results (from your code)
        model_probs = ml_results.get_player_probabilities()
        model_probs_str = model_probs if isinstance(model_probs, str) else str(model_probs)
        
        ml_predictions = f"""
        ML PREDICTION RESULTS:
        - Final Classification: {ml_results.get_final_prediction()}
        - Model Probabilities: {model_probs_str}
        - Model Confidence: {ml_results.get_pipeline_confidence()}
        """
        
        # User preferences
        preferences_dict = user_preferences.to_dict()
        pref_lines = []
        for k, v in preferences_dict.items():
            if v is not None:  # Only include non-None preferences
                # Format budget clearly as per-year amount
                if k == 'max_tuition_budget':
                    pref_lines.append(f"- {k}: ${v:,} per year")
                else:
                    pref_lines.append(f"- {k}: {v}")
        preferences_block = "\n".join(pref_lines) if pref_lines else "- (none provided)"
        
        # The Stage 1 prompt (adapted from your structure)
        prompt = f"""
        You are an expert college BASEBALL recruiting advisor. Your task is to generate 50 colleges that would be excellent fits for this baseball player based on their athletic ability, ML predictions, and personal preferences.
        
        USER PLAYER'S INFORMATION/STATS:
        {player_info}
        
        We used a proprietary machine learning model to make these predictions, predicting which level of baseball the student can play at in college.
        The model is trained on data from 2017-2023 and can predict with ~75-80% accuracy. The buckets predict what division the player can play at:
        - Power 4 (SEC, ACC, BIG 12, BIG 10 conferences) 
        - Non Power 4 Division 1 (all other D1 conferences)
        - Non Division 1 (D2, D3, JUCO, NAIA)
        
        MODEL PREDICTION:
        {ml_predictions}
        
        PLAYER PREFERENCES (must be respected in recommendations):
        {preferences_block}
        
        TASK: Generate 50 schools that would be excellent fits. Consider the following:
        
        1. ML PREDICTION ALIGNMENT: Respect the ML model confidence to determine school levels:
           - High confidence: ~90% of schools from predicted level, 10% stretch/safety
           - Medium confidence: ~80% from predicted level, 20% stretch/safety  
           - Low confidence: ~70% from predicted level, 30% stretch/safety
        
        2. PREFERENCE ALIGNMENT: Prioritize user preferences for:
           - Geographic regions and distance from home
           - Academic level and school size preferences
           - Financial constraints (tuition budget)
           - Campus life preferences
           - Athletic program quality preferences
        
        3. PLAYING TIME OPPORTUNITY: Consider schools where the player would have realistic chance for playing time based on:
           - Program level matching athletic ability
           - School's recent recruiting patterns
           - Position needs at the school
        
        4. PROGRAM FIT: Include schools with:
           - Strong baseball programs at appropriate competitive level
           - Good academic programs if important to player
           - Geographic distribution matching preferences
           - Mix of school sizes and settings
        
        Think through your reasoning for each school, considering how it matches the player's athletic ability, ML predictions, and personal preferences. Consider playing time opportunities, academic fit, geographic preferences, and program trajectory.
        
        However, ONLY return the list of 50 schools in this exact format using ABBREVIATED state names:
        
        ["School Name, City, ST", "School Name, City, ST", ...]
        
        IMPORTANT: Use 2-letter state abbreviations (NC, FL, GA, etc.) NOT full state names.
        Examples: "East Carolina University, Greenville, NC" or "University of South Florida, Tampa, FL"
        
        Return ONLY the Python list, nothing else. The list should contain exactly 50 schools.
        """
        
        return prompt
    
    def _parse_school_list(self, content: str) -> Optional[List[Tuple[str, str]]]:
        """Parse LLM response to extract school names and cities"""
        try:
            # Clean the response
            content = content.strip()
            
            # Handle code block formatting
            if '```' in content:
                start = content.find('[')
                end = content.rfind(']') + 1
                if start >= 0 and end > start:
                    content = content[start:end]
            
            # Find the JSON array in the content
            if not content.startswith('['):
                # Look for array start
                start = content.find('[')
                if start >= 0:
                    end = content.rfind(']') + 1
                    if end > start:
                        content = content[start:end]
            
            print(f"Parsing content: {content[:200]}...")
            
            # Parse as JSON/Python list
            import json
            try:
                school_list = json.loads(content)
            except json.JSONDecodeError:
                # Fallback to ast.literal_eval
                import ast
                school_list = ast.literal_eval(content)
            
            # Convert to (name, city) tuples
            parsed_schools = []
            for entry in school_list:
                if isinstance(entry, str):
                    # Handle format: "School Name, City, State"
                    parts = [p.strip() for p in entry.split(', ')]
                    if len(parts) >= 3:
                        # Assume last two parts are city, state
                        school_name = ', '.join(parts[:-2])  # Everything except last two
                        city_state = f"{parts[-2]}, {parts[-1]}"  # Last two parts
                        parsed_schools.append((school_name, city_state))
                    elif len(parts) == 2:
                        # Assume format is "School Name, Location"
                        school_name = parts[0]
                        city_state = parts[1]
                        parsed_schools.append((school_name, city_state))
                    else:
                        # Single name, no location info
                        parsed_schools.append((entry, "Unknown"))
            
            print(f"✅ Successfully parsed {len(parsed_schools)} schools from LLM response")
            for i, (name, location) in enumerate(parsed_schools[:5]):  # Show first 5
                print(f"  {i+1}. {name} - {location}")
            if len(parsed_schools) > 5:
                print(f"  ... and {len(parsed_schools) - 5} more")
            
            return parsed_schools
            
        except Exception as e:
            print(f"❌ Error parsing school list: {e}")
            print(f"Content sample: {content[:500]}")
            return None
    
    def _scrape_school_data(self, school_list: List[Tuple[str, str]]) -> Optional[List[SchoolInformation]]:
        """
        Stage 2: Scrape data for all schools with caching
        
        Args:
            school_list: List of (school_name, city_state) tuples
            
        Returns:
            List of SchoolInformation objects with scraped data
        """
        if not school_list:
            return None
        
        # Step 0: First do fuzzy matching to get actual matched school names (like background cache builder)
        print("  🔍 Performing fuzzy matching to get actual school names...")
        matched_schools = []
        for school_name, city_state in school_list:
            matched_name = self.scorecard_retriever.get_matched_school_name(school_name, city_state)
            if matched_name:
                matched_schools.append((school_name, matched_name, city_state))
                print(f"    ✅ {school_name} -> {matched_name}")
            else:
                # Use original name if no match found
                matched_schools.append((school_name, school_name, city_state))
                print(f"    ⚠️ {school_name} -> {school_name} (no fuzzy match)")
        
        # Use the actual matched names for all cache operations
        school_names = [matched[1] for matched in matched_schools]  # Use MATCHED names, not original
        
        try:
            # Step 1: Check cache for existing data using MATCHED names
            cached_data = {}
            schools_to_scrape = school_names
            
            if self.cache:
                print("  💾 Checking cache for existing school data using matched names...")
                cached_data, schools_to_scrape = self.cache.get_cached_school_data(school_names)
            
            # Step 2: Scrape only missing schools
            new_college_stats = {}
            new_niche_ratings = {}
            
            if schools_to_scrape:
                print(f"  📊 Scraping College Scorecard data for {len(schools_to_scrape)} schools...")
                
                # Get cities for schools that need scraping (map matched names back to cities)
                scrape_cities = []
                for school_name in schools_to_scrape:
                    # Find the city for this matched school name
                    city_found = None
                    for _, matched, city in matched_schools:
                        if matched == school_name:
                            city_found = city
                            break
                    scrape_cities.append(city_found)
                
                # Scrape College Scorecard data using matched names
                college_stats_list = self.scorecard_retriever.get_school_statistics(schools_to_scrape, scrape_cities)
                for i, school_name in enumerate(schools_to_scrape):
                    new_college_stats[school_name] = college_stats_list[i] if i < len(college_stats_list) else None
                
                print(f"  🎓 Scraping Niche ratings for {len(schools_to_scrape)} schools...")
                
                # Scrape Niche ratings
                new_niche_ratings = self.niche_scraper.scrape_multiple_schools(schools_to_scrape)
                
                # Step 3: Cache the newly scraped data
                if self.cache:
                    print("  💾 Caching newly scraped data...")
                    cache_pairs = []
                    for school_name in schools_to_scrape:
                        scorecard_data = new_college_stats.get(school_name)
                        niche_data = new_niche_ratings.get(school_name)
                        # Only cache if we have BOTH sources of data
                        if scorecard_data and niche_data:
                            cache_pairs.append((school_name, scorecard_data, niche_data))
                    
                    if cache_pairs:
                        self.cache.batch_cache_school_data(cache_pairs)
            
            # Step 4: Combine cached + newly scraped data
            combined_data = []
            for i, matched_name in enumerate(school_names):
                # Get the original GPT name for display purposes
                original_name = matched_name  # Default fallback
                for original, matched, _ in matched_schools:
                    if matched == matched_name:
                        original_name = original
                        break
                
                # Check if we have cached data (using matched name)
                if matched_name in cached_data:
                    scorecard_data, niche_data = self.cache.reconstruct_school_data(cached_data[matched_name])
                else:
                    # Use newly scraped data (using matched name)
                    scorecard_data = new_college_stats.get(matched_name)
                    niche_data = new_niche_ratings.get(matched_name)
                
                # Create SchoolInformation with original name for display, but data keyed by matched name
                school_info = SchoolInformation(
                    school_name=original_name,  # Use original GPT name for LLM consistency
                    school_stats=scorecard_data,
                    niche_ratings=niche_data
                )
                combined_data.append(school_info)
            
            return combined_data
            
        except Exception as e:
            print(f"Error scraping school data: {e}")
            return None
    
    def _generate_final_selection(
        self,
        player: PlayerType,
        ml_results: MLPipelineResults,
        user_preferences: UserPreferences,
        school_data: List[SchoolInformation]
    ) -> Optional[Dict[str, Any]]:
        """
        Stage 3: Final selection of 25 schools with detailed analysis
        """
        prompt = self._build_final_selection_prompt(
            player, ml_results, user_preferences, school_data
        )
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert college baseball recruitment advisor. Analyze the provided school data and return valid JSON with detailed recommendations."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            # Parse JSON response
            content = response.choices[0].message.content
            result = json.loads(content)
            
            # Add metadata
            result["generatedAt"] = datetime.now().isoformat()
            result["playerType"] = player.get_player_type()
            result["mlPrediction"] = ml_results.get_final_prediction()
            result["schoolsAnalyzed"] = len(school_data)
            
            return result
            
        except Exception as e:
            print(f"Error in final selection: {e}")
            return None
    
    def _build_final_selection_prompt(
        self,
        player: PlayerType,
        ml_results: MLPipelineResults,
        user_preferences: UserPreferences,
        school_data: List[SchoolInformation]
    ) -> str:
        """Build Stage 3 prompt with all school data"""
        
        # Reuse player info formatting from Stage 1
        player_info_dict = player.get_player_info()
        player_info = f"""
        PLAYER PROFILE:
        - Position: {player_info_dict.get('primary_position', 'N/A')}
        - Player Type: {player.get_player_type()}
        - Exit Velocity: {player_info_dict.get('exit_velo_max', 'N/A')} mph
        - 60-yard Time: {player_info_dict.get('sixty_time', 'N/A')} seconds
        - Height: {player_info_dict.get('height', 'N/A')} inches
        - Weight: {player_info_dict.get('weight', 'N/A')} lbs
        - Region: {player_info_dict.get('player_region', 'N/A')}
        """
        
        # Add position-specific info
        from backend.utils.player_types import PlayerCatcher, PlayerInfielder, PlayerOutfielder
        if isinstance(player, PlayerCatcher):
            player_info += f"\n- Catcher Velocity: {player_info_dict.get('c_velo', 'N/A')} mph"
            player_info += f"\n- Pop Time: {player_info_dict.get('pop_time', 'N/A')} seconds"
        elif isinstance(player, PlayerInfielder):
            player_info += f"\n- Infield Velocity: {player_info_dict.get('inf_velo', 'N/A')} mph"
        elif isinstance(player, PlayerOutfielder):
            player_info += f"\n- Outfield Velocity: {player_info_dict.get('of_velo', 'N/A')} mph"
        
        if user_preferences.hs_graduation_year:
            player_info += f"\n- Graduation Year: {user_preferences.hs_graduation_year}"

        # ML predictions
        model_probs = ml_results.get_player_probabilities()
        model_probs_str = model_probs if isinstance(model_probs, str) else str(model_probs)
        
        ml_predictions = f"""
        ML PREDICTION RESULTS:
        - Final Classification: {ml_results.get_final_prediction()}
        - Model Probabilities: {model_probs_str}
        - Model Confidence: {ml_results.get_pipeline_confidence()}
        """
        
        # User preferences
        preferences_dict = user_preferences.to_dict()
        pref_lines = []
        for k, v in preferences_dict.items():
            if v is not None:
                pref_lines.append(f"- {k}: {v}")
        preferences_block = "\n".join(pref_lines) if pref_lines else "- (none provided)"
        
        # Format all school data
        school_data_json = []
        for school in school_data:
            school_data_json.append(school.to_dict())
        
        # Build the final prompt (adapted from your detailed structure)
        prompt = f"""
        You are an expert college baseball recruiting advisor. You previously generated 50 schools for this player.
        Now you have detailed data for all 50 schools. Select the top 25 schools with detailed analysis.
        
        USER PLAYER'S INFORMATION/STATS:
        {player_info}
        
        MODEL PREDICTION:
        {ml_predictions}
        
        PLAYER PREFERENCES:
        {preferences_block}
        
        DETAILED SCHOOL DATA (College Scorecard + Niche ratings for all 50 schools):
        {json.dumps(school_data_json, indent=2)}
        
        TASK: Select the top 25 schools from the 50 provided, with detailed analysis.
        
        SELECTION CRITERIA:
        1. Athletic Fit (40%): How well does the player's ability match the program level?
        2. Academic Fit (20%): Does the school match academic preferences and admission requirements?
        3. Geographic/Financial Fit (20%): Alignment with location and cost preferences
        4. Program Quality (20%): Baseball program strength and development opportunity
        
        IMPORTANT FINANCIAL ANALYSIS:
        - All tuition amounts in the data are ANNUAL costs
        - Compare annual tuition against the player's annual budget (max_tuition_budget)
        - A school is "withinBudget" if annual tuition ≤ annual budget
        - For out-of-state students, use out_of_state_tuition for comparison
        
        Calculate a fitScore (0-100) for each selected school using these weightings.
        
        OUTPUT FORMAT - RETURN VALID JSON ONLY:
        {{
            "profileSummary": "2-3 sentence assessment of player's competitive level and recruiting prospects",
            "selectionSummary": "2-3 sentences explaining your selection methodology for these 25 schools",
            "schoolRecommendations": [
                {{
                    "name": "School Name",
                    "location": "City, State", 
                    "fitScore": 0,
                    "athleticFit": {{
                        "programLevel": "D1|D2|D3|NAIA|JUCO",
                        "competitiveness": "High|Medium|Low",
                        "reasoning": "Why this program matches player ability"
                    }},
                    "academicFit": {{
                        "admissionRate": "from data",
                        "averageSAT": "from data",
                        "academicRating": "from niche data",
                        "professionalRating": "from niche data",
                        "reasoning": "Academic fit assessment"
                    }},
                    "financialFit": {{
                        "inStateTuition": "from data",
                        "outOfStateTuition": "from data", 
                        "withinBudget": true|false,
                        "reasoning": "Financial fit assessment"
                    }},
                    "schoolProfile": {{
                        "enrollment": "from data",
                        "campusLife": "from niche ratings",
                        "athletics": "from niche ratings",
                        "location": "from niche ratings"
                    }},
                    "overallReasoning": "2-3 sentences explaining why this is an excellent fit",
                    "strengths": ["strength 1", "strength 2"],
                    "considerations": ["consideration 1", "consideration 2"]
                }}
                // ... exactly 25 schools, sorted by fitScore descending
            ]
        }}
        
        Return valid JSON only. Ensure exactly 25 schools in recommendations, sorted by fitScore.
        Use the actual data provided for each school in your analysis.
        """
        
        return prompt


# Example usage
if __name__ == "__main__":
    from backend.utils.prediction_types import D1PredictionResult, P4PredictionResult, MLPipelineResults
    from backend.utils.player_types import PlayerInfielder
    from backend.utils.preferences_types import UserPreferences
    
    # Create sample data
    sample_player = PlayerInfielder(
        height=72,
        weight=180,
        primary_position="SS",
        hitting_handedness="R",
        throwing_hand="R",
        region="Southeast",
        exit_velo_max=97.0,
        inf_velo=90.0,
        sixty_time=6.8
    )
    
    d1_result = D1PredictionResult(
        d1_probability=0.65,
        d1_prediction=True,
        confidence="High",
        model_version="inf_d1_v1.0"
    )
    
    p4_result = P4PredictionResult(
        p4_probability=0.25,
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
    
    sample_preferences = UserPreferences(
        user_state="NC",
        preferred_regions=["Southeast", "Midwest"],
        min_academic_rating="B+",
        max_budget=40000,
        hs_graduation_year="2026"
    )
    
    # Run pipeline
    pipeline = CollegeSelectionPipeline()
    result = pipeline.run_complete_pipeline(
        player=sample_player,
        ml_results=sample_ml_results,
        user_preferences=sample_preferences
    )
    
    if result:
        print("\n🎉 Pipeline completed successfully!")
        print(json.dumps(result, indent=2))
    else:
        print("\n❌ Pipeline failed")