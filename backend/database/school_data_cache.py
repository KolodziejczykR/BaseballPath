"""
School Data Cache using Supabase
Caches College Scorecard and Niche data to avoid repeated scraping
"""

import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from supabase import create_client, Client
from dotenv import load_dotenv

# Add project root to Python path
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.utils.scraping_types import SchoolStatisticsAPI, NicheRatings

# Load environment variables
load_dotenv()

class SchoolDataCache:
    """Supabase-based cache for school data to avoid repeated scraping"""
    
    def __init__(self):
        """Initialize Supabase client"""
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment variables")
        
        self.supabase: Client = create_client(url, key)
        self.table_name = "school_data_cache"
        
        # Cache expiry: 30 days
        self.cache_expiry_days = 30
    
    def get_cached_school_data(self, school_names: List[str]) -> Tuple[Dict[str, dict], List[str]]:
        """
        Get cached school data from Supabase
        
        Args:
            school_names: List of school names to check
            
        Returns:
            Tuple of (cached_data_dict, missing_schools_list)
            cached_data_dict maps school_name -> {scorecard_data, niche_data}
            missing_schools_list contains schools that need to be scraped
        """
        cached_data = {}
        missing_schools = []
        
        try:
            # Query for all requested schools
            response = self.supabase.table(self.table_name)\
                .select("*")\
                .in_("school_name", school_names)\
                .execute()
            
            if response.data:
                # Use timezone-aware datetime for comparison
                from datetime import timezone
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.cache_expiry_days)
                
                for record in response.data:
                    school_name = record["school_name"]
                    updated_at = datetime.fromisoformat(record["updated_at"].replace('Z', '+00:00'))
                    
                    # Check if data is still fresh
                    if updated_at > cutoff_date:
                        scorecard_data = record["scorecard_data"]
                        niche_data = record["niche_data"]
                        
                        cached_data[school_name] = {
                            "scorecard_data": scorecard_data,
                            "niche_data": niche_data
                        }
                        
                        # Show what data we have cached
                        data_status = []
                        if scorecard_data:
                            data_status.append("📊 Scorecard")
                        if niche_data and niche_data.get("overall_grade"):
                            data_status.append("🎓 Niche")
                        elif niche_data:
                            data_status.append("🎓 Niche (partial)")
                        
                        status_text = " + ".join(data_status) if data_status else "⚠️ No valid data"
                        age_days = (cutoff_date - updated_at).days + self.cache_expiry_days
                        print(f"  📋 Using cached data for {school_name} ({status_text}, {age_days}d old)")
                    else:
                        missing_schools.append(school_name)
                        age_days = (cutoff_date - updated_at).days + self.cache_expiry_days
                        print(f"  🕒 Cache expired for {school_name} ({age_days}d old)")
            
            # Add schools that weren't found in cache
            cached_school_names = set(cached_data.keys())
            for school_name in school_names:
                if school_name not in cached_school_names:
                    missing_schools.append(school_name)
                    print(f"  🆕 Not in cache: {school_name}")
            
            print(f"  ✅ Found {len(cached_data)} cached, need to scrape {len(missing_schools)}")
            if cached_data:
                print(f"  📋 Schools with cached data: {list(cached_data.keys())}")
            return cached_data, missing_schools
            
        except Exception as e:
            print(f"  ❌ Error retrieving cached data: {e}")
            # If cache fails, scrape all schools
            return {}, school_names
    
    def cache_school_data(self, school_name: str, scorecard_data: SchoolStatisticsAPI, niche_data: NicheRatings):
        """
        Cache school data in Supabase
        Only caches if Niche data was scraped successfully (no null values)
        
        Args:
            school_name: Name of the school
            scorecard_data: College Scorecard statistics
            niche_data: Niche ratings and information
        """
        try:
            # Check if niche data has null/invalid values (indicating failed scraping)
            if niche_data and self._has_null_niche_values(niche_data):
                print(f"  ⚠️ Skipping cache for {school_name}: Niche data contains null values")
                return
            
            # Convert data to JSON-serializable format
            scorecard_json = scorecard_data.to_dict() if scorecard_data else None
            niche_json = niche_data.to_dict() if niche_data else None
            
            # Prepare record for upsert
            record = {
                "school_name": school_name,
                "scorecard_data": scorecard_json,
                "niche_data": niche_json,
                "updated_at": datetime.now().isoformat()
            }
            
            # Upsert (insert or update) the record
            response = self.supabase.table(self.table_name)\
                .upsert(record, on_conflict="school_name")\
                .execute()
            
            if response.data:
                print(f"  💾 Cached data for: {school_name}")
            
        except Exception as e:
            print(f"  ❌ Error caching data for {school_name}: {e}")
            # Don't fail the pipeline if caching fails
            pass
    
    def batch_cache_school_data(self, school_data_pairs: List[Tuple[str, SchoolStatisticsAPI, NicheRatings]]):
        """
        Cache multiple schools' data in a batch operation
        Only caches schools where Niche data was scraped successfully (no null values)
        
        Args:
            school_data_pairs: List of (school_name, scorecard_data, niche_data) tuples
        """
        if not school_data_pairs:
            return
        
        try:
            records = []
            skipped_count = 0
            
            for school_name, scorecard_data, niche_data in school_data_pairs:
                # Check if niche data has null/invalid values (indicating failed scraping)
                if niche_data and self._has_null_niche_values(niche_data):
                    print(f"  ⚠️ Skipping batch cache for {school_name}: Niche data contains null values")
                    skipped_count += 1
                    continue
                
                # Convert data to JSON-serializable format
                scorecard_json = scorecard_data.to_dict() if scorecard_data else None
                niche_json = niche_data.to_dict() if niche_data else None
                
                records.append({
                    "school_name": school_name,
                    "scorecard_data": scorecard_json,
                    "niche_data": niche_json,
                    "updated_at": datetime.now().isoformat()
                })
            
            # Batch upsert
            response = self.supabase.table(self.table_name)\
                .upsert(records, on_conflict="school_name")\
                .execute()
            
            if response.data:
                cached_count = len(records)
                total_count = len(school_data_pairs)
                print(f"  💾 Batch cached data for {cached_count}/{total_count} schools")
                if skipped_count > 0:
                    print(f"  ⚠️ Skipped {skipped_count} schools due to null Niche data")
            
        except Exception as e:
            print(f"  ❌ Error batch caching data: {e}")
            # Don't fail the pipeline if caching fails
            pass
    
    def reconstruct_school_data(self, cached_data: dict) -> Tuple[Optional[SchoolStatisticsAPI], Optional[NicheRatings]]:
        """
        Reconstruct SchoolStatisticsAPI and NicheRatings objects from cached JSON
        
        Args:
            cached_data: Dict with 'scorecard_data' and 'niche_data' keys
            
        Returns:
            Tuple of (SchoolStatisticsAPI, NicheRatings) or (None, None) if reconstruction fails
        """
        try:
            scorecard_obj = None
            niche_obj = None
            
            # Reconstruct SchoolStatisticsAPI
            if cached_data.get("scorecard_data"):
                sc_data = cached_data["scorecard_data"]
                scorecard_obj = SchoolStatisticsAPI(
                    school_city=sc_data.get("school_city", "Unknown"),
                    undergrad_enrollment=sc_data.get("undergrad_enrollment", 0),
                    in_state_tuition=sc_data.get("in_state_tuition", 0),
                    out_of_state_tuition=sc_data.get("out_of_state_tuition", 0),
                    admission_rate=sc_data.get("admission_rate", 0.0),
                    avg_sat=sc_data.get("avg_sat", 0),
                    avg_act=sc_data.get("avg_act", 0)
                )
            
            # Reconstruct NicheRatings
            if cached_data.get("niche_data"):
                niche_data = cached_data["niche_data"]
                niche_obj = NicheRatings(
                    school_name=niche_data.get("school_name", ""),
                    overall_grade=niche_data.get("overall_grade"),
                    academics_grade=niche_data.get("academics_grade"),
                    campus_life_grade=niche_data.get("campus_life_grade"),
                    overall_athletics_grade=niche_data.get("athletics_grade"),
                    value_grade=niche_data.get("value_grade"),
                    student_life_grade=niche_data.get("student_life_grade"),
                    party_scene_grade=niche_data.get("party_scene_grade"),
                    diversity_grade=niche_data.get("diversity_grade"),
                    location_grade=niche_data.get("location_grade"),
                    safety_grade=niche_data.get("safety_grade"),
                    professors_grade=niche_data.get("professors_grade"),
                    dorms_grade=niche_data.get("dorms_grade"),
                    campus_food_grade=niche_data.get("campus_food_grade"),
                    enrollment=niche_data.get("enrollment"),
                    niche_url=niche_data.get("niche_url"),
                    error=niche_data.get("error")
                )
            
            return scorecard_obj, niche_obj
            
        except Exception as e:
            print(f"  ❌ Error reconstructing cached data: {e}")
            return None, None

    def _has_null_niche_values(self, niche_data: NicheRatings) -> bool:
        """
        Check if Niche data has too many null values indicating failed scraping
        For smaller schools, only reject if more than half of the grades are null

        Args:
            niche_data: NicheRatings object to check

        Returns:
            True if more than half grades are null, False if acceptable data
        """
        if not niche_data:
            return True

        # Check if error field is set
        if niche_data.error:
            return True

        # Check grade fields specifically (same logic as missing_schools builders)
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

        # Return True if data should be rejected (less than half grades present)
        return len(valid_grades) < min_required_grades


def create_school_data_cache_table():
    """
    Create the school_data_cache table in Supabase
    Run this once to set up the table structure
    """
    print("Creating school_data_cache table in Supabase...")
    
    # This would typically be done through Supabase SQL editor:
    sql_create_table = """
    CREATE TABLE IF NOT EXISTS school_data_cache (
        id SERIAL PRIMARY KEY,
        school_name TEXT UNIQUE NOT NULL,
        scorecard_data JSONB,
        niche_data JSONB,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    -- Create index on school_name for faster lookups
    CREATE INDEX IF NOT EXISTS idx_school_data_cache_name ON school_data_cache(school_name);
    
    -- Create index on updated_at for cache expiry checks
    CREATE INDEX IF NOT EXISTS idx_school_data_cache_updated ON school_data_cache(updated_at);
    """
    
    print("Execute this SQL in your Supabase SQL editor:")
    print(sql_create_table)


if __name__ == "__main__":
    # Print table creation SQL
    create_school_data_cache_table()