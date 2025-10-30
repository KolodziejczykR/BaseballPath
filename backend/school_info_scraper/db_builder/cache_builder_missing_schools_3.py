"""
Background School Cache Builder
Efficiently pre-populates Supabase cache with popular schools to reduce pipeline scraping load.
"""

import os
import sys
import time
import random
from typing import List, Tuple, Optional
from datetime import datetime

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.database.school_data_cache import SchoolDataCache
from backend.school_info_scraper.college_scoreboard_retrieval import CollegeScorecardRetriever
from backend.school_info_scraper.niche_bs_scraper import NicheBSScraper


class BackgroundCacheBuilder:
    """Builds cache by scraping popular schools with human-like timing patterns"""
    
    def __init__(self):
        self.process_id = "D3_BUILDER"
        self.cache = SchoolDataCache()
        self.scorecard_api = CollegeScorecardRetriever()
        # D3 Builder - Safari macOS configuration
        self.niche_scraper = NicheBSScraper(
            delay=0.5,
        )
        self.session_counter = 0
        self.total_processed = 0
        self.session_rotation_limit = 5  # Rotate every 5 schools
        self.delay_range = (110, 180)  # 110-180 seconds
        
    def get_popular_schools_list(self) -> List[str]:
        """
        Returns a comprehensive list of popular schools to cache
        Building the database for d3 schools
        """
        schools = [
            "Presbyterian College, Clinton, SC",
            "Principia College, Elsah, IL",
            "Penn State Abington, Abington, PA",
            "Penn State Altoona, Altoona, PA",
            "Penn State Behrend, Erie, PA",
            "Penn State Berks, Reading, PA",
            "Penn State Harrisburg, Middletown, PA",
            "Purdue University Northwest, Westville, IN",
            "Queens University, Charlotte, NC",
            "University of Richmond, Richmond, VA",
            "Rivier University, Nashua, NH",
            "Rockford University, Rockford, IL",
            "Rose-Hulman Institute of Technology, Terre Haute, IN",
            "Rosemont College, Bryn Mawr, PA",
            "Russell Sage College, Troy, NY",
            "Southern Arkansas University, Magnolia, AR",
            "Southern Connecticut State University, New Haven, CT",
            "San Francisco State University, San Fransisco, CA",
            "University of Southern Maine, Portland, ME",
            "Southern Virginia University, Buena Vista, VA",
            "Salem University, Salem, WV",
            "Salisbury University, Salisbury, MD",
            "University of South Carolina Aiken, Aiken, SC",
            "University of South Carolina Beaufort, Bluffton, SC",
            "University of South Carolina Upstate, Spartanburg, SC",
            "Schreiner University, Kerrville, TX",
            "Sewanee: The University Of The South, Sewanee, TN",
            "Shepherd University, Shepherdstown, WV",
            "Simpson College, Indianola, IA",
            "University of Sioux Falls, Sioux Falls, SD",
            "Slippery Rock University, Slippery Rock, PA",
            "Southern Nazarene University, Bethany, OK",
            "Southern University, Baton Rouge, LA",
            "Spalding University, Louisville, KY",
            "Springfield College, Springfield, MA",
            "St. Bonaventure University, St Bonaventure, NY",
            "St. Cloud State University, St. Cloud, MN",
            "St. Edward's University, Austin, TX",
            "Saint Elizabeth University, Morristown, NJ",
            "St. John Fisher University, Rochester, NY",
            "St. Joseph's University, New York - Long Island, Patchogue, NY",
            "St. Joseph's University, New York -Brooklyn, Brooklyn, NY",
            "Saint Joseph's College, Standish, ME",
            "St. Lawrence University, Canton, NY",
            "St. Mary's College, St Marys City, MD",
            "St. Mary's University, San Antonio, TX",
            "St. Norbert College, De Pere, WI",
            "St. Olaf College, Northfield, MN",
            "The College of St. Scholastica, Duluth, MN",
            "University of St. Thomas, St Paul, MN",
            "University of St. Thomas - Texas, Houston, TX",
            "Saint Vincent College, Latrobe, PA",
            "College of Staten Island, Staten Island, NY",
            "Stevenson University, Owings Mills, MD",
            "Sul Ross State University, Alpine, TX",
            "SUNY Canton, Canton, NY",
            "SUNY Cobleskill, Cobleskill, NY",
            "SUNY Cortland, Cortland, NY",
            "SUNY at New Paltz, New Paltz, NY",
            "SUNY Old Westbury, Old Westbury, NY",
            "SUNY Oswego, Oswego, NY",
            "SUNY Plattsburgh, Plattsburgh, NY",
            "SUNY Polytechnic Institute, Utica, NY",
            "Southwest Minnesota State University, Marshall, MN",
            "Tennessee Tech University, Cookeville, TN",
            "Thiel College, Greenville, PA",
            "Thomas College, Waterville, ME",
            "Thomas More University, Crestview Hills, KY",
            "Troy University, Troy, AL",
            "Texas Lutheran University, Seguin, TX",
            "Texas Southern University, Houston, TX",
            "University of California-Davis, Davis, CA",
            "University of California-Riverside, Riverside, CA",
            "University of California San Diego, San Diego, CA",
            "University of California-Santa Barbara, Santa Barbara, CA",
            "University of the Ozarks, Clarksville, AR",
            "Upper Iowa University, Fayette, IA",
            "The University of Texas at Dallas, Richardson, TX",
            "The University of Texas at Tyler, Tyler, TX",
            "Utah Tech University, St. George, UT",
            "The University of Virginia's College at Wise, Wise, VA",
            "University of Valley Forge, Phoenixville, PA",
            "University of Virginia-Charlottesville, Charlottesville, VA", #University of Virginia
            "Western New England University, Springfield, MA",
            "Washington College, Chestertown, MD",
            "Washington University in St. Louis, St. Louis, MO",
            "Wayne State College, Wayne, NE",
            "Waynesburg University, Waynesburg, PA",
            "Webster University, Webster Groves, MO",
            "Wentworth Institute of Technology, Boston, MA",
            "University of West Georgia, Carrollton, GA",
            "Westminster College - Missouri, Fulton, MO",
            "Westminster College - Pennsylvania, Wilmington, PA",
            "Wheaton College - Illinois, Wheaton, IL",
            "Wheaton College - Massachusetts, Norton, MA",
            "Whitman College, Walla Walla, WA",
            "Wisconsin Lutheran College, Milwaukee, WI",
            "University of Wisconsin-Parkside, Kenosha, WI",
            "University of Wisconsin-Superior, Superior, WI",
            "Widener University, Chester, PA",
            "Wilmington College, Wilmington, OH",
            "Wilson College, Chambersburg, PA",
            "Winona State University, Winona, MN",
            "Jessup University, Rocklin, CA",
            "The College of Wooster, Wooster, OH",
            "Worcester State University, Worcester, MA",
            "West Virginia Wesleyan College, Buckhannon, WV",
            "York College of Pennsylvania, York, PA",
            "Young Harris College, Young Harris, GA"
        ]

        return schools
    
    def fuzzy_match_cities(self, schools_list: List[str]) -> List[Tuple[str, str]]:
        """
        Perform fuzzy city matching just like the pipeline does
        Returns list of (original_school_string, matched_school_name) tuples
        """
        matched_schools = []
        
        print(f"\n🔍 Starting fuzzy city matching for {len(schools_list)} schools...")
        
        for school_string in schools_list:
            try:
                # Parse school info (format: "School Name, City, State")
                parts = school_string.split(", ")
                if len(parts) >= 3:
                    school_name = parts[0].strip()
                    city = parts[1].strip() 
                    state = parts[2].strip()
                    city_state = f"{city}, {state}"
                    
                    # Get the actual matched school name using our helper method
                    matched_name = self._get_actual_matched_school_name(school_name, city_state)
                    
                    if matched_name:
                        matched_schools.append((school_string, matched_name))
                        print(f"  ✅ Matched: {school_string} -> {matched_name}")
                    else:
                        print(f"  ❌ No match found for: {school_string}")
                        
                elif len(parts) >= 2:
                    # Handle format with just school and location
                    school_name = parts[0].strip()
                    location = parts[1].strip()
                    
                    matched_name = self._get_actual_matched_school_name(school_name, location)
                    
                    if matched_name:
                        matched_schools.append((school_string, matched_name))
                        print(f"  ✅ Matched: {school_string} -> {matched_name}")
                    else:
                        print(f"  ❌ No match found for: {school_string}")
                else:
                    print(f"  ❌ Invalid format: {school_string}")
                    
            except Exception as e:
                print(f"  ❌ Error matching {school_string}: {e}")
        
        print(f"🎯 Successfully matched {len(matched_schools)} out of {len(schools_list)} schools")
        return matched_schools
    
    def _get_actual_matched_school_name(self, school_name: str, city_state: str = None) -> Optional[str]:
        """
        Get the actual matched school name from College Scorecard API
        Returns the official school name that was matched, not the input name
        """
        try:
            return self.scorecard_api.get_matched_school_name(school_name, city_state)
        except Exception as e:
            print(f"    ⚠️ Error getting matched name for {school_name}: {e}")
            return None
    
    def _validate_niche_data(self, niche_data) -> bool:
        """
        Validate that Niche data contains meaningful information (not just NULL values)
        For smaller schools, only reject if more than half of the grades are null

        Args:
            niche_data: NicheRatings object to validate

        Returns:
            True if data is valid and meaningful, False if more than half grades are null
        """
        if not niche_data:
            return False

        # Check grade fields specifically (excluding enrollment for this calculation)
        grade_fields = [
            niche_data.overall_grade,
            niche_data.academics_grade,
            niche_data.campus_life_grade,
            niche_data.overall_athletics_grade,
            niche_data.value_grade,
            niche_data.student_life_grade,
            niche_data.diversity_grade,
            niche_data.location_grade,
            niche_data.safety_grade,
            niche_data.professors_grade,
            niche_data.dorms_grade,
            niche_data.campus_food_grade
        ]

        # Count non-null, non-empty grade fields
        valid_grades = [field for field in grade_fields if field and str(field).strip()]

        # For smaller schools, accept data if more than half of grades are present
        # 12 total grades, so need at least 6 grades to be valid (50%+ threshold)
        min_required_grades = len(grade_fields) // 2

        return len(valid_grades) >= min_required_grades
    
    def filter_uncached_schools(self, matched_schools: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Remove schools that are already cached"""
        school_names = [school_name for _, school_name in matched_schools]
        cached_data, missing_schools = self.cache.get_cached_school_data(school_names)
        
        # Filter to only uncached schools
        uncached_schools = [(orig, name) for orig, name in matched_schools if name in missing_schools]
        
        print(f"📊 Cache status: {len(cached_data)} cached, {len(uncached_schools)} need scraping")
        return uncached_schools
    
    def scrape_and_cache_school(self, school_name: str) -> bool:
        """
        Scrape both College Scorecard and Niche data for a school and immediately cache it
        Returns True if successful, False if failed
        """
        print(f"\n🔄 Processing: {school_name}")
        
        try:
            # Fetch College Scorecard data using the correct API
            print(f"  📊 Fetching College Scorecard data...")
            scorecard_results = self.scorecard_api.get_school_statistics([school_name])
            scorecard_data = scorecard_results[0] if scorecard_results and len(scorecard_results) > 0 else None
            
            if scorecard_data and scorecard_data.undergrad_enrollment > 500:
                print(f"  ✅ College Scorecard: Found data for {school_name}")
            else:
                print(f"  ❌ College Scorecard: No data found")
                scorecard_data = None
            
            # Fetch Niche data with random delay (D3 specific timing)
            delay = random.randint(*self.delay_range)
            print(f"  ⏱️ [{self.process_id}] Waiting {delay} seconds before Niche scraping...")
            time.sleep(delay)
            
            print(f"  🎓 Fetching Niche data...")
            niche_data = self.niche_scraper.scrape_school_ratings(school_name)
            
            if niche_data and not niche_data.error:
                # Validate that we got meaningful data (not just NULL values)
                if self._validate_niche_data(niche_data):
                    print(f"  ✅ Niche: Successfully scraped {school_name}")
                else:
                    print(f"  ❌ Niche: Scrape failed - only NULL values returned for {school_name}")
                    niche_data = None  # Don't cache incomplete data
            else:
                error_msg = niche_data.error if niche_data else "Unknown error"
                print(f"  ❌ Niche: Failed to scrape {school_name} - {error_msg}")
                niche_data = None
            
            # Only cache if we have BOTH College Scorecard AND Niche data
            if scorecard_data and niche_data:
                print(f"  💾 Caching complete data for {school_name}")
                self.cache.cache_school_data(school_name, scorecard_data, niche_data)
                return True
            else:
                missing_sources = []
                if not scorecard_data:
                    missing_sources.append("College Scorecard")
                if not niche_data:
                    missing_sources.append("Niche")
                
                print(f"  ❌ Not caching {school_name} - missing: {', '.join(missing_sources)}")
                return False
            
        except Exception as e:
            print(f"  💥 Error processing {school_name}: {e}")
            return False
    
    def rotate_session(self):
        """Rotate the scraping session to avoid detection"""
        print(f"\n🔄 [{self.process_id}] Rotating session (processed {self.session_counter} schools this session)")
        try:
            # Close session (requests session doesn't need explicit close but we can clear it)
            if hasattr(self.niche_scraper, 'session'):
                self.niche_scraper.session.close()
            time.sleep(random.randint(80, 125))  # Brief pause between sessions (D3 timing)
            # Reinitialize with D3 configuration (user agent randomized internally)
            self.niche_scraper = NicheBSScraper(delay=0.5)
            self.session_counter = 0
        except Exception as e:
            print(f"  ⚠️ [{self.process_id}] Session rotation warning: {e}")
    
    def take_break(self, minutes: int = 15):
        """Take a longer break to simulate human behavior"""
        print(f"\n☕ Taking {minutes}-minute break (processed {self.total_processed} schools total)")
        time.sleep(minutes * 60)
    
    def run_background_caching(self):
        """
        Main method to run the background caching process
        """
        print(f"🚀 Starting Background School Cache Builder [{self.process_id}]")
        print("=" * 60)
        
        # Get schools list
        schools_list = self.get_popular_schools_list()
        print(f"📝 Loaded {len(schools_list)} popular schools")
        
        # Fuzzy match cities
        matched_schools = self.fuzzy_match_cities(schools_list)
        
        if not matched_schools:
            print("❌ No schools matched. Exiting.")
            return
        
        # Filter out cached schools
        uncached_schools = self.filter_uncached_schools(matched_schools)
        
        if not uncached_schools:
            print("✅ All schools already cached! Nothing to do.")
            return
        
        # Randomize the order
        random.shuffle(uncached_schools)
        
        print(f"\n🎯 [{self.process_id}] Starting to process {len(uncached_schools)} uncached schools...")
        print(f"📋 Strategy:")
        print(f"   • Random delays: {self.delay_range[0]}-{self.delay_range[1]} seconds between Niche requests")
        print(f"   • Session rotation: Every {self.session_rotation_limit} schools")
        print(f"   • Break time: 15-20 minutes every 35-40 schools")
        print(f"   • User Agent: Safari macOS")
        print(f"   • Immediate caching: Each school cached before moving to next")
        
        successful_schools = 0
        failed_schools = 0
        failed_school_list = []  # Track failed schools with reasons
        start_time = datetime.now()

        try:
            for i, (original_string, school_name) in enumerate(uncached_schools, 1):
                print(f"\n{'='*50}")
                print(f"School {i}/{len(uncached_schools)} - {school_name}")
                print(f"Original: {original_string}")
                print(f"Progress: {i/len(uncached_schools)*100:.1f}%")
                
                # Process the school
                success = self.scrape_and_cache_school(school_name)

                if success:
                    successful_schools += 1
                else:
                    failed_schools += 1
                    # Track failed school for summary
                    failed_school_list.append({
                        'name': school_name,
                        'original': original_string
                    })
                
                self.session_counter += 1
                self.total_processed += 1
                
                # Session rotation (D3 specific frequency)
                if self.session_counter >= self.session_rotation_limit:
                    self.rotate_session()
                
                # Take break every 27 schools (D3 pattern)
                if i % 27 == 0 and i < len(uncached_schools):
                    self.take_break(random.randint(15, 20))  # 15-20 minute break
                
                # Progress summary every 10 schools
                if i % 10 == 0:
                    elapsed = datetime.now() - start_time
                    rate = i / elapsed.total_seconds() * 3600  # schools per hour
                    print(f"\n📈 Progress Summary:")
                    print(f"   • Processed: {i}/{len(uncached_schools)} schools")
                    print(f"   • Success rate: {successful_schools}/{i} ({successful_schools/i*100:.1f}%)")
                    print(f"   • Rate: {rate:.1f} schools/hour")
                    print(f"   • Elapsed: {elapsed}")
        
        except KeyboardInterrupt:
            print(f"\n⏹️ Process interrupted by user")
        
        except Exception as e:
            print(f"\n💥 Unexpected error: {e}")
        
        finally:
            # Final summary
            total_time = datetime.now() - start_time
            print(f"\n🏁 Background Caching Complete!")
            print(f"=" * 60)
            print(f"✅ Successfully processed: {successful_schools}")
            print(f"❌ Failed: {failed_schools}")
            print(f"⏱️ Total time: {total_time}")
            print(f"📊 Success rate: {successful_schools/(successful_schools+failed_schools)*100:.1f}%")

            # Print failed schools list
            if failed_school_list:
                print(f"\n{'='*60}")
                print(f"FAILED SCHOOLS ({len(failed_school_list)}):")
                print(f"{'='*60}")
                for idx, failed_school in enumerate(failed_school_list, 1):
                    print(f"{idx}. {failed_school['name']}")
                    print(f"   Original: {failed_school['original']}")
            else:
                print(f"\n🎉 No failed schools!")

            # Close resources
            try:
                if hasattr(self.niche_scraper, 'session'):
                    self.niche_scraper.session.close()
            except:
                pass


if __name__ == "__main__":
    builder = BackgroundCacheBuilder()
    builder.run_background_caching()