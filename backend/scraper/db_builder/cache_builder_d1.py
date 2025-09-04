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
        Based on Power 4, major conferences, and popular recruiting targets
        """
        schools = [
            # Power 4 - SEC
            "University of Alabama, Tuscaloosa, AL",
            "Auburn University, Auburn, AL", 
            "University of Arkansas, Fayetteville, AR",
            "University of Florida, Gainesville, FL",
            "University of Georgia, Athens, GA",
            "University of Kentucky, Lexington, KY",
            "Louisiana State University, Baton Rouge, LA",
            "University of Mississippi, Oxford, MS",
            "Mississippi State University, Starkville, MS",
            "University of Missouri, Columbia, MO",
            "University of South Carolina, Columbia, SC",
            "University of Tennessee - Knoxville, Knoxville, TN",
            "Texas A&M University, College Station, TX",
            "Vanderbilt University, Nashville, TN",
            
            # Power 4 - ACC
            "Boston University, Boston, MA",
            "Carnegie Mellon University, Pittsburgh, PA",
            "Boston College, Chestnut Hill, MA",
            "Clemson University, Clemson, SC",
            "Duke University, Durham, NC",
            "Florida State University, Tallahassee, FL",
            "Georgia Institute of Technology, Atlanta, GA",
            "University of Louisville, Louisville, KY",
            "University of Miami, Coral Gables, FL",
            "North Carolina State University, Raleigh, NC",
            "University of North Carolina at Chapel Hill, Chapel Hill, NC",
            "University of Notre Dame, Notre Dame, IN",
            "University of Pittsburgh, Pittsburgh, PA",
            "Virginia Tech, Blacksburg, VA",
            "University of Virginia-Charlottesville, Charlottesville, VA",
            "Wake Forest University, Winston-Salem, NC",
            
            # Power 4 - Big Ten
            "University of Illinois, Champaign, IL",
            "Indiana University, Bloomington, IN",
            "University of Iowa, Iowa City, IA",
            "University of Maryland, College Park, MD",
            "University of Michigan, Ann Arbor, MI",
            "Michigan State University, East Lansing, MI",
            "University of Minnesota, Minneapolis, MN",
            "University of Nebraska-Lincoln, Lincoln, NE",
            "Northwestern University, Evanston, IL",
            "Ohio State University-Main Campus, Columbus, OH",
            "Pennsylvania State University, University Park, PA",
            "Purdue University, West Lafayette, IN",
            "Rutgers University, New Brunswick, NJ",
            "University of Wisconsin, Madison, WI",
            
            # Power 4 - Big 12
            "Baylor University, Waco, TX",
            "University of Cincinnati, Cincinnati, OH",
            "University of Houston, Houston, TX",
            "Iowa State University, Ames, IA",
            "University of Kansas, Lawrence, KS",
            "Kansas State University, Manhattan, KS",
            "Oklahoma State University, Stillwater, OK",
            "Texas Christian University, Fort Worth, TX",
            "Texas Tech University, Lubbock, TX",
            "University of Texas at Austin, Austin, TX",
            "West Virginia University, Morgantown, WV",
            
            # Power 4 - Pac-12/West
            "Arizona State University, Tempe, AZ",
            "University of Arizona, Tucson, AZ",
            "University of California Berkeley, Berkeley, CA",
            "University of California Los Angeles, Los Angeles, CA",
            "University of Colorado, Boulder, CO",
            "University of Oregon, Eugene, OR",
            "Oregon State University, Corvallis, OR",
            "Stanford University, Stanford, CA",
            "University of Southern California, Los Angeles, CA",
            "University of Utah, Salt Lake City, UT",
            "University of Washington, Seattle, WA",
            "Washington State University, Pullman, WA",
            
            # Major Mid-Major D1 Conferences
            "East Carolina University, Greenville, NC",
            "University of North Carolina at Charlotte, Charlotte, NC",
            "Old Dominion University, Norfolk, VA",
            "Virginia Commonwealth University, Richmond, VA",
            "College of Charleston, Charleston, SC",
            "University of North Carolina Wilmington, Wilmington, NC",
            "James Madison University, Harrisonburg, VA",
            "Liberty University, Lynchburg, VA",
            "Coastal Carolina University, Conway, SC",
            "University of South Alabama, Mobile, AL",
            
            # Popular Northeast Schools
            "University of Connecticut, Storrs, CT",
            "Northeastern University, Boston, MA",
            "University of Massachusetts, Amherst, MA",
            "University of Rhode Island, Kingston, RI",
            "University of Vermont, Burlington, VT",
            "University of Maine, Orono, ME",
            "University of New Haven, West Haven, CT",
            "Merrimack College, North Andover, MA",
            "Quinnipiac University, Hamden, CT",
            "Rhode Island College, Providence, RI",
            "St. John's University, Queens, NY",
            "Fordham University, Bronx, NY",
            "Iona College, New Rochelle, NY",
            "Marist College, Poughkeepsie, NY",
            "Canisius College, Buffalo, NY",
            "Niagara University, Lewiston, NY",
            "Siena College, Loudonville, NY",
            "University at Albany, Albany, NY",
            "Stony Brook University, Stony Brook, NY",
            "Binghamton University, Binghamton, NY",
            "Hofstra University, Hempstead, NY",
            "Yeshiva University, New York, NY",
            "Fairleigh Dickinson University, Madison, NJ",
            "Rutgers University Newark, Newark, NJ",
            "Seton Hall University, South Orange, NJ",
            "Montclair State University, Montclair, NJ",
            "Rowan University, Glassboro, NJ",
            "The College of New Jersey, Ewing, NJ",
            "Stevens Institute of Technology, Hoboken, NJ",
            "New Jersey Institute of Technology, Newark, NJ",
            "St. Peter's University, Jersey City, NJ",
            "Monmouth University, West Long Branch, NJ",
            "Rensselaer Polytechnic Institute, Troy, NY",
            "Catholic University of America, Washington, DC",
            "Skidmore College, Saratoga Springs, NY",
            "Union College, Schenectady, NY",
            "Ithaca College, Ithaca, NY",
            "University of New Hampshire, Durham, NH",
            "Fairfield University, Fairfield, CT",
            "Sacred Heart University, Fairfield, CT",
            
            # Popular California Schools
            "California State University-Fullerton, Fullerton, CA",
            "University of California-Irvine, Irvine, CA",
            "University of California-San Diego, San Diego, CA",
            "San Diego State University, San Diego, CA",
            "California Polytechnic State University, San Luis Obispo, CA",
            "Pepperdine University, Malibu, CA",
            "Loyola Marymount University, Los Angeles, CA",
            "University of San Diego, San Diego, CA",
            
            # Popular Texas Schools
            "Rice University, Houston, TX",
            "University of Texas at San Antonio, San Antonio, TX",
            "Texas State University, San Marcos, TX",
            "University of Texas at Dallas, Richardson, TX",
            "Sam Houston State University, Huntsville, TX",
            "Stephen F. Austin State University, Nacogdoches, TX",
            "Texas A&M University Corpus Christi, Corpus Christi, TX",
            "University of Texas at Arlington, Arlington, TX",
            "Trinity University, San Antonio, TX",
            "University of Mary Hardin-Baylor, Belton, TX",
            
            # Popular Florida Schools
            "Florida International University, Miami, FL",
            "Florida Atlantic University, Boca Raton, FL",
            "University of Central Florida, Orlando, FL",
            "University of South Florida, Tampa, FL",
            "University of North Florida, Jacksonville, FL",
            "Florida Gulf Coast University, Fort Myers, FL",
            "University of Central Florida, Orlando, FL",
            "Florida Institute of Technology, Melbourne, FL",
            "Stetson University, DeLand, FL",
            
            # Popular Mid-Atlantic Schools
            "George Washington University, Washington, DC",
            "Georgetown University, Washington, DC",
            "George Mason University, Fairfax, VA",
            "Towson University, Towson, MD",
            "University of Delaware, Newark, DE",
            "Drexel University, Philadelphia, PA",
            "Temple University, Philadelphia, PA",
            "Villanova University, Villanova, PA",
            
            # Popular Midwest Schools
            "Creighton University, Omaha, NE",
            "Bradley University, Peoria, IL",
            "University of Evansville, Evansville, IN",
            "Butler University, Indianapolis, IN",
            "Xavier University, Cincinnati, OH",
            "University of Dayton, Dayton, OH",
            
            # Popular Mountain West Schools
            "University of Nevada Las Vegas, Las Vegas, NV",
            "Colorado State University, Fort Collins, CO",
            "Air Force Academy, Colorado Springs, CO",
            "Brigham Young University, Provo, UT",
            
            # Ivy League and Elite Academic Schools  
            "Harvard University, Cambridge, MA",
            "Yale University, New Haven, CT",
            "Princeton University, Princeton, NJ",
            "Columbia University, New York, NY",
            "University of Pennsylvania, Philadelphia, PA",
            "Dartmouth College, Hanover, NH",
            "Brown University, Providence, RI",
            "Cornell University, Ithaca, NY",

            "University of San Francisco, San Francisco, CA",
            "Santa Clara University, Santa Clara, CA",
            "University of Portland, Portland, OR",
            "Loyola University Chicago, Chicago, IL",
            "University of Illinois Chicago, Chicago, IL",
            "Belmont University, Nashville, TN",
            "Murray State University, Murray, KY",
            "Southern Illinois University, Carbondale, IL",
            "Illinois State University, Normal, IL",
            "Bradley University, Peoria, IL",  # you had it under Midwest, keep
            "Ball State University, Muncie, IN",
            "Miami University, Oxford, OH",
            "Kent State University, Kent, OH",
            "Bowling Green State University, Bowling Green, OH",
            "University of Toledo, Toledo, OH",
            "Central Michigan University, Mount Pleasant, MI",
            "Eastern Michigan University, Ypsilanti, MI",
            "Western Michigan University, Kalamazoo, MI",
            "Northern Illinois University, DeKalb, IL",
            "University of Akron, Akron, OH",
            "University of Buffalo, Buffalo, NY",
            "University of Maine, Orono, ME",  # already included
            "University of Hartford, Hartford, CT",
            "Manhattan College, Riverdale, NY",
            "Fairfield University, Fairfield, CT",  # already in your list
            "Sacred Heart University, Fairfield, CT",  # already in your list
            "Bryant University, Smithfield, RI",
            "Long Island University, Brooklyn, NY",
            "Central Connecticut State University, New Britain, CT",
            "Mount St. Mary’s University, Emmitsburg, MD",
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