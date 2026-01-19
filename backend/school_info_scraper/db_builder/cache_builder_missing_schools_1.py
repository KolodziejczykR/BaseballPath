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

from supabase import create_client, Client
from dotenv import load_dotenv
from backend.school_info_scraper.college_scoreboard_retrieval import CollegeScorecardRetriever
from backend.school_info_scraper.niche_bs_scraper import NicheBSScraper

# Load environment variables from project root
load_dotenv(os.path.join(project_root, '.env'))


class BackgroundCacheBuilder:
    """Builds cache by scraping popular schools with human-like timing patterns"""

    def __init__(self):
        self.process_id = "D3_BUILDER"

        # Initialize Supabase client
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        self.supabase: Client = create_client(url, key)
        self.table_name = "school_data_general"

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
            "Alfred University, Alfred, NY",
            "Alfred State College, Alfred, NY",
            "Anderson University, Anderson, IN",
            "Anderson University, Anderson, SC",
            "Anna Maria College, Paxton, MA",
            "University of Arkansas at Little Rock, Little Rock, AR",
            "University of Arkansas at Monticello, Monticello, AR",
            "University of Arkansas at Pine Bluff, Pine Bluff, AR",
            "Arkansas State University, Jonesboro, AR",
            "Arkansas Tech University, Russellville, AR",
            "University of Arkansas - Fort Smith, Fort Smith, AR",
            "United States Military Academy, West Point, NY",
            "Asbury University, Wilmore, KY",
            "Augsburg University, Minneapolis, MN",
            "Augustana College, Rock Island, IL",
            "Augustana University, Sioux Falls, SD",
            "Aurora University, Aurora, IL",
            "Averett University, Danville, VA",
            "Bard College, Dutchess County, NY",
            "Baruch College, New York, NY",
            "Belhaven University, Jackson, MS",
            "Beloit College, Beloit, WI",
            "Bemidji State University, Bemidji, MN",
            "Benedict College, Columbia, SC",
            "Benedictine University, Lisle, IL",
            "Berea College, Berea, KY",
            "Bethany Lutheran College, Mankato, MN",
            "Bethany College, Bethany, WV",
            "Bethel University, Saint Paul, MN",
            "Blackburn_College, Carlinville, IL", 
            "Commonwealth University-Bloomsburg, Bloomsburg, PA", #Bloomsburg University
            "Bluffton University, Bluffton, OH",
            "Bob Jones University, Greenville, SC",
            "Brevard College, Brevard, NC",
            "University of Bridgeport, Bridgeport, CT",
            "Cairn University, Langhorne, PA",
            "California State University-Los Angeles, Los Angeles, CA",
            "Pennsylvania Western University, California, PA",
            "Capital University, Bexley, OH",
            "Carroll University, Waukesha, WI",
            "Vermont State University Castleton, Castleton, VT",
            "Catawba College, Salisbury, NC",
            "University of Central Arkansas, Conway, AR",
            "Centenary College, Shreveport, LA",
            "Centenary University, Hackettstown, NJ",
            "Chaminade University, Honolulu, HI",
            "Charleston Southern University, Charleston, SC",
            "Chestnut Hill College, Philadelphia, PA",
            "The Citadel, Charleston, SC",
            "The City College of New York, New York, NY",
            "PennWest Clarion, Clarion, PA", #Clarion University
            "Clark Atlanta University, Atlanta, GA",
            "United States Coast Guard Academy, New London, CT", #Coast Guard Academy
            "Coker University, Hartsville, SC",
            "Colby-Sawyer College, New London, NH",
            "Concordia University Chicago, River Forest, IL",
            "Concordia University St. Paul, Saint Paul, MN",
            "Concordia University Texas, Austin, TX",
            "Concordia University Wisconsin, Mequon, WI",
            "Cornell College, Mount Vernon, IA",
            "SUNY Cortland, Cortland, NY",
            "Covenant College, Lookout Mountain, GA",
            "Crown College, St Bonifacius, MN",
            "California State University-Chico, Chico, CA",
            "California State University-Dominguez Hills, Carson, CA",
            "California State University-Monterey Bay, Seaside, CA",
            "California State Polytechnic University-Pomona, Pomona, CA", #Cal Poly-Pomona
            "California State University-San Bernardino, San Bernardino, CA",
            "California State University-San Marcos, San Marcos, CA",
            "California State University-Stanislaus, Turlock, CA",
            "California State University-Easy Bay, Hayward, CA",
            "Dallas Baptist University, Dallas, TX",
            "Dean College, Franklin, MA",
            "Dominican University, River Forest, IL",
            "Dubuque University, Dubuque, IA",
            "Eastern Illinois University, Charleston, IL",
            "Eastern New Mexico University, Portales, NM",
            "East Texas Baptist University, Marshall, TX",
            "East Central University, Ada, OK",
            "Eastern University, St Davids, PA",
            "Eckerd College, St. Petersburg, FL",
            "Edgewood University, Madison, WI",
            "Elizabethtown College. Elizabethtown, PA",
            "Elms College, Chicopee, MA",
            "Emerson College, Boston, MA",
            "Emmanuel University, Franklin Springs, GA",
            "East Tennessee State University, Johnson City, TN",
            "Eureka College, Eureka, IL",
            "Fairleigh Dickinson University, Teaneck, NJ",
            "Farmingdale State College, Farmingdale, NY",
            "Ferrum College, Ferrum, VA",
            "University of Findlay, Findlay, OH",
            "Flagler College, St. Augustine, FL",
            "Florida A&M University, Tallahassee, FL",
            "Framingham State University, Framingham, MA",
            "Franciscan University of Steubenville, Steubenville, OH",
            "Gardner-Webb University, Boiling Springs, NC",
            "Geneva College, Beaver Falls, PA",
            "Grambling State University, Grambling, LA",
            "Greensboro College, Greensboro, NC",
            "Greenville University, Greenville, IL",
            "Guilford College, Greensboro, NC",
            "Gwynedd Mercy University, Gwynedd Valley, PA",
            "Hardin-Simmons University, Abilene, TX",
            "University of Hawaii at Hilo, Hilo, HI",
            "Hawaii Pacific University, Honolulu, HI",
            "High Point University, High Point, NC",
            "Hilbert College, Hamburg, NY",
            "Hillsdale College, Hillsdale, MI"
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
            niche_data.total_athletics_grade,
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
        """Remove schools that are already in school_data_general"""
        school_names = [school_name for _, school_name in matched_schools]

        # Query school_data_general to see which schools already exist
        try:
            response = self.supabase.table(self.table_name)\
                .select("school_name")\
                .in_("school_name", school_names)\
                .execute()

            existing_schools = set([record["school_name"] for record in response.data]) if response.data else set()
        except Exception as e:
            print(f"  ⚠️ Error checking existing schools: {e}")
            existing_schools = set()

        # Filter to only schools not in database
        uncached_schools = [(orig, name) for orig, name in matched_schools if name not in existing_schools]

        print(f"📊 Database status: {len(existing_schools)} already exist, {len(uncached_schools)} need scraping")
        return uncached_schools
    
    def scrape_and_cache_school(self, school_name: str) -> bool:
        """
        Scrape both College Scorecard and Niche data for a school and immediately insert into school_data_general
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

            # DEBUG: Print all field values (even if NULL)
            if niche_data:
                print(f"  🔍 DEBUG - Niche data for {school_name}:")
                print(f"      overall_grade: '{niche_data.overall_grade}'")
                print(f"      academics_grade: '{niche_data.academics_grade}'")
                print(f"      campus_life_grade: '{niche_data.campus_life_grade}'")
                print(f"      total_athletics_grade: '{niche_data.total_athletics_grade}'")
                print(f"      value_grade: '{niche_data.value_grade}'")
                print(f"      student_life_grade: '{niche_data.student_life_grade}'")
                print(f"      diversity_grade: '{niche_data.diversity_grade}'")
                print(f"      location_grade: '{niche_data.location_grade}'")
                print(f"      safety_grade: '{niche_data.safety_grade}'")
                print(f"      professors_grade: '{niche_data.professors_grade}'")
                print(f"      dorms_grade: '{niche_data.dorms_grade}'")
                print(f"      campus_food_grade: '{niche_data.campus_food_grade}'")
                print(f"      party_scene_grade: '{niche_data.party_scene_grade}'")
                print(f"      enrollment: '{niche_data.enrollment}'")
                print(f"      error: '{niche_data.error}'")

            # Track failure reason
            failure_reason = None

            if niche_data and not niche_data.error:
                # Validate that we got meaningful data (not just NULL values)
                if self._validate_niche_data(niche_data):
                    print(f"  ✅ Niche: Successfully scraped {school_name}")
                else:
                    print(f"  ⚠️ Niche: Validation failed - insufficient data for {school_name}")
                    failure_reason = "null values"
                    niche_data = None
            else:
                # Has error or no data
                error_msg = niche_data.error if niche_data else "Unknown error"
                print(f"  ❌ Niche: Failed to scrape {school_name} - {error_msg}")
                if niche_data and "404" in str(niche_data.error):
                    failure_reason = "invalid niche link"
                else:
                    failure_reason = "scraping error"
                niche_data = None

            # Only insert if we have BOTH College Scorecard AND Niche data
            if scorecard_data and niche_data:
                print(f"  💾 Inserting complete data for {school_name} into school_data_general")

                # Split school_city into city and state (format: "City, ST")
                city_parts = scorecard_data.school_city.split(', ') if scorecard_data.school_city else [None, None]
                school_city = city_parts[0] if len(city_parts) > 0 else None
                school_state = city_parts[1] if len(city_parts) > 1 else None

                # Prepare record for insertion (id will be auto-generated by database)
                record = {
                    "school_name": school_name,
                    "school_city": school_city,
                    "school_state": school_state,
                    "undergrad_enrollment": scorecard_data.undergrad_enrollment,
                    "in_state_tuition": scorecard_data.in_state_tuition,
                    "out_of_state_tuition": scorecard_data.out_of_state_tuition,
                    "admission_rate": float(scorecard_data.admission_rate) if scorecard_data.admission_rate else None,
                    "avg_sat": scorecard_data.avg_sat,
                    "avg_act": scorecard_data.avg_act,
                    "overall_grade": niche_data.overall_grade,
                    "academics_grade": niche_data.academics_grade,
                    "total_athletics_grade": niche_data.total_athletics_grade,
                    "value_grade": niche_data.value_grade,
                    "location_grade": niche_data.location_grade,
                    "student_life_grade": niche_data.student_life_grade,
                    "party_scene_grade": niche_data.party_scene_grade,
                    "campus_life_grade": niche_data.campus_life_grade,
                    "campus_food_grade": niche_data.campus_food_grade,
                    "professors_grade": niche_data.professors_grade,
                    "diversity_grade": niche_data.diversity_grade,
                    "safety_grade": niche_data.safety_grade,
                    "dorms_grade": niche_data.dorms_grade
                }

                # Insert into school_data_general
                response = self.supabase.table(self.table_name).insert(record).execute()

                if response.data:
                    print(f"  ✅ Successfully inserted {school_name} into school_data_general")
                    return True, None
                else:
                    print(f"  ❌ Failed to insert {school_name}")
                    return False, "database insertion failed"
            else:
                missing_sources = []
                if not scorecard_data:
                    missing_sources.append("College Scorecard")
                    if not failure_reason:
                        failure_reason = "missing scorecard data"
                if not niche_data:
                    missing_sources.append("Niche")
                    # failure_reason already set above if niche failed

                print(f"  ❌ Not inserting {school_name} - missing: {', '.join(missing_sources)}")
                return False, failure_reason

        except Exception as e:
            print(f"  💥 Error processing {school_name}: {e}")
            return False, f"exception: {str(e)}"
    
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
                success, failure_reason = self.scrape_and_cache_school(school_name)

                if success:
                    successful_schools += 1
                else:
                    failed_schools += 1
                    # Track failed school for summary
                    failed_school_list.append({
                        'name': school_name,
                        'original': original_string,
                        'reason': failure_reason or "unknown"
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
                    print(f"{idx}. {failed_school['name']} ({failed_school['reason']})")
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