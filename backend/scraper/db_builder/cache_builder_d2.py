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
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.database.school_data_cache import SchoolDataCache
from backend.scraper.college_scoreboard_retrieval import CollegeScorecardRetriever
from backend.scraper.niche_bs_scraper import NicheBSScraper


class BackgroundCacheBuilder:
    """Builds cache by scraping popular schools with human-like timing patterns"""
    
    def __init__(self):
        self.cache = SchoolDataCache()
        self.scorecard_api = CollegeScorecardRetriever()
        self.niche_scraper = NicheBSScraper(delay=0)  # We'll handle timing manually
        self.session_counter = 0
        self.total_processed = 0
        
    def get_popular_schools_list(self) -> List[str]:
        """
        Returns a comprehensive list of popular schools to cache
        Building the database for d2 schools
        """
        schools = [
            "University of Tampa, Tampa, FL",
            "Rollins College, Winter Park, FL",
            "Florida Southern College, Lakeland, FL",
            "Barry University, Miami Shores, FL",
            "Nova Southeastern University, Fort Lauderdale, FL",
            "Eckerd College, St. Petersburg, FL",
            "Lynn University, Boca Raton, FL",
            "Embry-Riddle Aeronautical University, Daytona Beach, FL",
            "Flagler College, St. Augustine, FL",
            "Valdosta State University, Valdosta, GA",
            "Columbus State University, Columbus, GA",
            "University of West Georgia, Carrollton, GA",
            "Georgia College and State University, Milledgeville, GA",
            "Augusta University, Augusta, GA",
            "University of North Georgia, Dahlonega, GA",
            "Young Harris College, Young Harris, GA",
            "University of West Florida, Pensacola, FL",
            "Delta State University, Cleveland, MS",
            "University of Montevallo, Montevallo, AL",
            "University of West Alabama, Livingston, AL",
            "Spring Hill College, Mobile, AL",
            "Shorter University, Rome, GA",
            "Lee University, Cleveland, TN",
            "Carson-Newman University, Jefferson City, TN",
            "Lincoln Memorial University, Harrogate, TN",
            "Tusculum University, Greeneville, TN",
            "Trevecca Nazarene University, Nashville, TN",
            "Kentucky Wesleyan College, Owensboro, KY",
            "Ashland University, Ashland, OH",
            "University of Findlay, Findlay, OH",
            "Cedarville University, Cedarville, OH",
            "Tiffin University, Tiffin, OH",
            "Walsh University, North Canton, OH",
            "Malone University, Canton, OH",
            "Lake Erie College, Painesville, OH",
            "Ohio Dominican University, Columbus, OH",
            "Wayne State University, Detroit, MI",
            "Grand Valley State University, Allendale, MI",
            "Saginaw Valley State University, University Center, MI",
            "Ferris State University, Big Rapids, MI",
            "Northwood University, Midland, MI",
            "Davenport University, Grand Rapids, MI",
            "Northern Michigan University, Marquette, MI",
            "Michigan Tech University, Houghton, MI",
            "University of Indianapolis, Indianapolis, IN",
            "University of Southern Indiana, Evansville, IN",
            "Bellarmine University, Louisville, KY",
            "Southern Nazarene University, Bethany, OK",
            "Southwestern Oklahoma State University, Weatherford, OK",
            "Northeastern State University, Tahlequah, OK",
            "East Central University, Ada, OK",
            "University of Central Oklahoma, Edmond, OK",
            "University of Central Missouri, Warrensburg, MO",
            "Northwest Missouri State University, Maryville, MO",
            "Missouri Southern State University, Joplin, MO",
            "Missouri Western State University, St. Joseph, MO",
            "Lincoln University of Missouri, Jefferson City, MO",
            "Truman State University, Kirksville, MO",
            "Emporia State University, Emporia, KS",
            "Pittsburg State University, Pittsburg, KS",
            "Fort Hays State University, Hays, KS",
            "Washburn University, Topeka, KS",
            "Newman University, Wichita, KS",
            "University of Nebraska at Kearney, Kearney, NE",
            "Wayne State College, Wayne, NE",
            "Northern State University, Aberdeen, SD",
            "University of Sioux Falls, Sioux Falls, SD",
            "Augustana University, Sioux Falls, SD",
            "Minot State University, Minot, ND",
            "University of Mary, Bismarck, ND",
            "Concordia University St. Paul, St. Paul, MN",
            "Winona State University, Winona, MN",
            "Bemidji State University, Bemidji, MN",
            "Southwest Minnesota State University, Marshall, MN",
            "St. Cloud State University, St. Cloud, MN",
            "Upper Iowa University, Fayette, IA",
            "Wayne State University, Wayne, MI",
            "Rockhurst University, Kansas City, MO",
            "Drury University, Springfield, MO",
            "Maryville University, St. Louis, MO",
            "Missouri S&T, Rolla, MO",
            "Southern Arkansas University, Magnolia, AR",
            "Henderson State University, Arkadelphia, AR",
            "Ouachita Baptist University, Arkadelphia, AR",
            "Arkansas Tech University, Russellville, AR",
            "Southeastern Oklahoma State University, Durant, OK",
            "Texas A&M University-Commerce, Commerce, TX",
            "Angelo State University, San Angelo, TX",
            "West Texas A&M University, Canyon, TX",
            "Lubbock Christian University, Lubbock, TX",
            "St. Edward's University, Austin, TX",
            "St. Mary's University, San Antonio, TX",
            "Texas A&M International University, Laredo, TX",
            "Oklahoma Christian University, Edmond, OK",
            "Rogers State University, Claremore, OK",
            "Harding University, Searcy, AR",
            "Henderson State University, Arkadelphia, AR",
            "Christian Brothers University, Memphis, TN",
            "Union University, Jackson, TN",
            "Houston Christian University, Houston, TX",
            "Palm Beach Atlantic University, West Palm Beach, FL",
            "Barry University, Miami Shores, FL",
            "Lenoir-Rhyne University, Hickory, NC",
            "Catawba College, Salisbury, NC",
            "Wingate University, Wingate, NC",
            "Belmont Abbey College, Belmont, NC",
            "Queens University of Charlotte, Charlotte, NC",
            "Mount Olive University, Mount Olive, NC",
            "Barton College, Wilson, NC",
            "North Greenville University, Tigerville, SC",
            "Erskine College, Due West, SC",
            "Newberry College, Newberry, SC",
            "Lander University, Greenwood, SC",
            "Francis Marion University, Florence, SC",
            "Anderson University, Anderson, SC",
            "Chowan University, Murfreesboro, NC",
            "Shepherd University, Shepherdstown, WV",
            "West Liberty University, West Liberty, WV",
            "Wheeling University, Wheeling, WV",
            "Charleston University, Charleston, WV",
            "Fairmont State University, Fairmont, WV",
            "Glenville State University, Glenville, WV",
            "Concord University, Athens, WV",
            "Bluefield State University, Bluefield, WV",
            "Davis & Elkins College, Elkins, WV",
            "West Virginia State University, Institute, WV",
            "Salem University, Salem, WV"
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
        
        Args:
            niche_data: NicheRatings object to validate
            
        Returns:
            True if data is valid and meaningful, False if only NULL values
        """
        if not niche_data:
            return False
        
        # Check for at least some meaningful data (not all None/empty)
        meaningful_fields = [
            niche_data.overall_grade,
            niche_data.academics_grade,
            niche_data.campus_life_grade,
            niche_data.athletics_grade,
            niche_data.value_grade,
            niche_data.student_life_grade,
            niche_data.diversity_grade,
            niche_data.location_grade,
            niche_data.safety_grade,
            niche_data.professors_grade,
            niche_data.dorms_grade,
            niche_data.campus_food_grade,
            niche_data.enrollment
        ]
        
        # Consider data valid if at least 3 meaningful fields have non-None, non-empty values
        valid_fields = [field for field in meaningful_fields if field and str(field).strip()]
        
        return len(valid_fields) >= 3
    
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
            
            # Fetch Niche data with random delay
            delay = random.randint(60, 150)  # 1-2.5 minutes
            print(f"  ⏱️ Waiting {delay} seconds before Niche scraping...")
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
        print(f"\n🔄 Rotating session (processed {self.session_counter} schools this session)")
        try:
            # Close session (requests session doesn't need explicit close but we can clear it)
            if hasattr(self.niche_scraper, 'session'):
                self.niche_scraper.session.close()
            time.sleep(random.randint(30, 60))  # Brief pause between sessions
            self.niche_scraper = NicheBSScraper(delay=0)
            self.session_counter = 0
        except Exception as e:
            print(f"  ⚠️ Session rotation warning: {e}")
    
    def take_break(self, minutes: int = 15):
        """Take a longer break to simulate human behavior"""
        print(f"\n☕ Taking {minutes}-minute break (processed {self.total_processed} schools total)")
        time.sleep(minutes * 60)
    
    def run_background_caching(self):
        """
        Main method to run the background caching process
        """
        print("🚀 Starting Background School Cache Builder")
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
        
        print(f"\n🎯 Starting to process {len(uncached_schools)} uncached schools...")
        print(f"📋 Strategy:")
        print(f"   • Random delays: 120-240 seconds between Niche requests")
        print(f"   • Session rotation: Every 5 schools (increased stealth)")
        print(f"   • Break time: 15 minutes every 30 schools")
        print(f"   • Immediate caching: Each school cached before moving to next")
        
        successful_schools = 0
        failed_schools = 0
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
                
                self.session_counter += 1
                self.total_processed += 1
                
                # Session rotation every 5 schools
                if self.session_counter >= 5:
                    self.rotate_session()
                
                # Take break every 30 schools
                if i % 30 == 0 and i < len(uncached_schools):
                    self.take_break(10)  # 10-minute break
                
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
            
            # Close resources
            try:
                if hasattr(self.niche_scraper, 'session'):
                    self.niche_scraper.session.close()
            except:
                pass


if __name__ == "__main__":
    builder = BackgroundCacheBuilder()
    builder.run_background_caching()