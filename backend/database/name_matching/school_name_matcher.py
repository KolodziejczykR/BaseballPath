"""
School Name to Baseball Rankings Name Matcher
Matches school names from school_data_general to team names in baseball_rankings_data
Following the specified matching algorithm with exact and fuzzy matching
"""

import os
import sys
import re
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from supabase import create_client, Client
from dotenv import load_dotenv

from rapidfuzz import fuzz, process
FUZZY_LIB = 'rapidfuzz'

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SchoolNameMatcher:
    """Matches school names to baseball rankings team names using exact and fuzzy matching"""

    def __init__(self):
        """Initialize Supabase client and load data"""
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")

        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

        self.supabase: Client = create_client(url, key)
        self.school_names = []
        self.team_names = []

        logger.info(f"Using fuzzy matching library: {FUZZY_LIB}")

    def normalize_school_name(self, school_name: str) -> str:
        """
        Normalize school name by removing common prefixes/postfixes

        Algorithm:
        1. Remove prefix "University of" or postfixes "University", "College"
        2. Turn "State University" → "St"
        3. Remove city and state portion (after comma)

        Examples:
        - "University of California, Berkeley, CA" → "California"
        - "Stanford University, Stanford, CA" → "Stanford"
        - "Arizona State University, Tempe, AZ" → "Arizona St"
        - "Boston College, Chestnut Hill, MA" → "Boston"
        """
        # First, remove the city, state portion (everything after first comma)
        if ',' in school_name:
            school_name = school_name.split(',')[0].strip()

        # Normalize whitespace
        school_name = ' '.join(school_name.split())

        # Handle "State University" → "St" (must be done before removing "University")
        # Match patterns like "Arizona State University", "Iowa State University"
        state_uni_pattern = r'^(.+?)\s+State\s+University$'
        state_match = re.match(state_uni_pattern, school_name, re.IGNORECASE)
        if state_match:
            base_name = state_match.group(1).strip()
            return f"{base_name} St"

        # Remove "University of" prefix
        university_of_pattern = r'^University\s+of\s+(.+)$'
        uni_of_match = re.match(university_of_pattern, school_name, re.IGNORECASE)
        if uni_of_match:
            school_name = uni_of_match.group(1).strip()

        # Remove "University" postfix
        if school_name.endswith(' University'):
            school_name = school_name[:-11].strip()

        # Remove "College" postfix
        if school_name.endswith(' College'):
            school_name = school_name[:-8].strip()

        return school_name.strip()

    def fetch_school_names(self) -> List[str]:
        """Fetch all unique school names from school_data_general"""
        logger.info("Fetching school names from school_data_general...")
        try:
            response = self.supabase.table('school_data_general')\
                .select('school_name')\
                .execute()

            if not response.data:
                logger.warning("No school names found in school_data_general")
                return []

            school_names = [row['school_name'] for row in response.data if row.get('school_name')]
            unique_names = sorted(list(set(school_names)))
            logger.info(f"✅ Fetched {len(unique_names)} unique school names from school_data_general")
            return unique_names

        except Exception as e:
            logger.error(f"❌ Error fetching school names: {e}")
            raise

    def fetch_unmatched_school_names(self) -> List[str]:
        """
        Fetch school names that are in school_data_general AND have NULL team_name
        in the mapping table (need to be rematched)
        """
        logger.info("Fetching unmatched school names (NULL team_name)...")
        try:
            # First get all school names from school_data_general
            all_schools = self.fetch_school_names()

            # Then get schools that already have mappings with NULL team_name
            response = self.supabase.table('school_baseball_ranking_name_mapping')\
                .select('school_name')\
                .is_('team_name', 'null')\
                .execute()

            if not response.data:
                logger.info("No schools with NULL team_name found in mapping table")
                return all_schools  # Return all schools if none have been processed

            unmatched_schools = [row['school_name'] for row in response.data]

            # Filter to only include schools that are still in school_data_general
            valid_unmatched = [s for s in unmatched_schools if s in all_schools]

            logger.info(f"✅ Found {len(valid_unmatched)} schools with NULL team_name that need matching")
            return sorted(valid_unmatched)

        except Exception as e:
            logger.error(f"❌ Error fetching unmatched schools: {e}")
            # If there's an error (e.g., table doesn't exist), return all schools
            logger.info("Falling back to all schools from school_data_general")
            return self.fetch_school_names()

    def fetch_team_names(self) -> List[str]:
        """Fetch all unique team names from baseball_rankings_data"""
        logger.info("Fetching team names from baseball_rankings_data...")
        try:
            response = self.supabase.table('baseball_rankings_data')\
                .select('team_name')\
                .execute()

            if not response.data:
                logger.warning("No team names found in baseball_rankings_data")
                return []

            team_names = [row['team_name'] for row in response.data if row.get('team_name')]
            unique_names = sorted(list(set(team_names)))
            logger.info(f"✅ Fetched {len(unique_names)} unique team names")
            return unique_names

        except Exception as e:
            logger.error(f"❌ Error fetching team names: {e}")
            raise

    def find_exact_match(self, normalized_name: str, team_names: List[str]) -> Optional[str]:
        """
        Look for exact match (case-insensitive) in team names

        Args:
            normalized_name: The normalized school name
            team_names: List of team names to search

        Returns:
            Matched team name if found, None otherwise
        """
        normalized_lower = normalized_name.lower()

        for team_name in team_names:
            if team_name.lower() == normalized_lower:
                return team_name

        return None

    def find_fuzzy_match(self, normalized_name: str, team_names: List[str],
                        threshold: float = 90.0) -> Optional[Tuple[str, float]]:
        """
        Find fuzzy match using ratio-based fuzzy string matching
        Only returns match if confidence is above threshold (90%)

        Args:
            normalized_name: The normalized school name
            team_names: List of team names to search
            threshold: Minimum confidence score (0-100)

        Returns:
            Tuple of (matched_team_name, confidence_score) if above threshold, None otherwise
        """
        # Use extractOne to find best match
        result = process.extractOne(
            normalized_name,
            team_names,
            scorer=fuzz.ratio
        )

        if result is None:
            return None

        matched_name, score = result[0], result[1]

        # Only return if score is above threshold
        if score >= threshold:
            logger.debug(f"Fuzzy match: '{normalized_name}' → '{matched_name}' (score: {score:.1f}%)")
            return (matched_name, score / 100.0)  # Convert to 0-1 scale

        return None

    def match_school_to_team(self, school_name: str, team_names: List[str]) -> Dict:
        """
        Match a single school name to a team name using the algorithm:
        1. Check if original school_name matches any team_name (case-insensitive)
        2. Normalize school name
        3. Try exact match with normalized name
        4. If no exact match, try fuzzy match (>90% confidence)
        5. If no qualifying match, return no_match

        Args:
            school_name: Original school name from school_data_general
            team_names: List of all team names from baseball_rankings_data

        Returns:
            Dictionary with match results
        """
        # Step 0: Check if original school_name (case-insensitive) matches any team_name
        original_match = self.find_exact_match(school_name, team_names)
        if original_match:
            logger.debug(f"Original name match: '{school_name}' → '{original_match}'")
            return {
                'school_name': school_name,
                'team_name': original_match,
                'match_type': 'exact_original',
                'confidence_score': None,
                'normalized_school_name': school_name,  # No normalization needed
                'verified': None
            }

        # Normalize the school name for further matching
        normalized = self.normalize_school_name(school_name)

        # Step 1: Try exact match with normalized name
        exact_match = self.find_exact_match(normalized, team_names)
        if exact_match:
            return {
                'school_name': school_name,
                'team_name': exact_match,
                'match_type': 'exact',
                'confidence_score': None,
                'normalized_school_name': normalized,
                'verified': None
            }

        # Step 2: Try fuzzy match (90% threshold)
        fuzzy_match = self.find_fuzzy_match(normalized, team_names, threshold=90.0)
        if fuzzy_match:
            matched_name, confidence = fuzzy_match
            return {
                'school_name': school_name,
                'team_name': matched_name,
                'match_type': 'fuzzy',
                'confidence_score': confidence,
                'normalized_school_name': normalized,
                'verified': None  # Needs manual review
            }

        # Step 3: No qualifying match found
        logger.debug(f"No match found for: '{school_name}' (normalized: '{normalized}')")
        return {
            'school_name': school_name,
            'team_name': None,
            'match_type': 'no_match',
            'confidence_score': None,
            'normalized_school_name': normalized,
            'verified': None  # Needs manual review
        }

    def match_all_schools(self, only_unmatched: bool = True) -> List[Dict]:
        """
        Match all schools from school_data_general to baseball_rankings_data

        Args:
            only_unmatched: If True, only process schools with NULL team_name in mapping table

        Returns:
            List of match result dictionaries
        """
        logger.info("=" * 80)
        logger.info("Starting school name matching process...")
        logger.info("=" * 80)

        # Fetch data
        if only_unmatched:
            self.school_names = self.fetch_unmatched_school_names()
        else:
            self.school_names = self.fetch_school_names()

        self.team_names = self.fetch_team_names()

        if not self.school_names:
            logger.info("✅ No unmatched schools found - all schools already have matches!")
            return []

        if not self.team_names:
            logger.error("No team names to match against!")
            return []

        # Match each school
        results = []
        total_schools = len(self.school_names)

        logger.info(f"\nMatching {total_schools} schools to {len(self.team_names)} teams...")
        logger.info("-" * 80)

        for i, school_name in enumerate(self.school_names, 1):
            if i % 50 == 0:
                logger.info(f"Progress: {i}/{total_schools} schools processed...")

            match_result = self.match_school_to_team(school_name, self.team_names)
            results.append(match_result)

        # Print summary statistics
        self._print_summary(results)

        return results

    def _print_summary(self, results: List[Dict]):
        """Print summary statistics of matching results"""
        exact_original_matches = sum(1 for r in results if r['match_type'] == 'exact_original')
        exact_matches = sum(1 for r in results if r['match_type'] == 'exact')
        fuzzy_matches = sum(1 for r in results if r['match_type'] == 'fuzzy')
        no_matches = sum(1 for r in results if r['match_type'] == 'no_match')
        total = len(results)

        if total == 0:
            logger.info("\nNo schools to process!")
            return

        logger.info("\n" + "=" * 80)
        logger.info("MATCHING SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total schools processed: {total}")
        logger.info(f"Exact matches (original name): {exact_original_matches} ({exact_original_matches/total*100:.1f}%)")
        logger.info(f"Exact matches (normalized): {exact_matches} ({exact_matches/total*100:.1f}%)")
        logger.info(f"Fuzzy matches (>90%): {fuzzy_matches} ({fuzzy_matches/total*100:.1f}%)")
        logger.info(f"No matches found: {no_matches} ({no_matches/total*100:.1f}%)")
        total_matched = exact_original_matches + exact_matches + fuzzy_matches
        logger.info(f"\nTotal matched: {total_matched} ({total_matched/total*100:.1f}%)")
        logger.info(f"Needs manual review: {fuzzy_matches + no_matches} ({(fuzzy_matches + no_matches)/total*100:.1f}%)")
        logger.info("=" * 80)

    def upload_to_database(self, results: List[Dict], use_update: bool = True):
        """
        Upload matching results to school_baseball_ranking_name_mapping table

        Args:
            results: List of match result dictionaries
            use_update: If True, UPDATE existing records. If False, INSERT new records
        """
        logger.info("\n" + "=" * 80)
        logger.info("Uploading results to database...")
        logger.info("=" * 80)

        if not results:
            logger.warning("No results to upload!")
            return

        total_results = len(results)
        successful_updates = 0
        failed_updates = 0

        logger.info(f"Processing {total_results} records...")
        logger.info(f"Mode: {'UPDATE existing records' if use_update else 'INSERT new records'}")
        logger.info("-" * 80)

        # Process each record individually for UPDATE operations
        for i, record in enumerate(results, 1):
            if i % 50 == 0:
                logger.info(f"Progress: {i}/{total_results} records processed...")

            try:
                if use_update:
                    # UPDATE existing record by school_name
                    response = self.supabase.table('school_baseball_ranking_name_mapping')\
                        .update({
                            'team_name': record['team_name'],
                            'match_type': record['match_type'],
                            'confidence_score': record['confidence_score'],
                            'normalized_school_name': record['normalized_school_name'],
                            'verified': record['verified']
                        })\
                        .eq('school_name', record['school_name'])\
                        .execute()
                else:
                    # INSERT new record
                    response = self.supabase.table('school_baseball_ranking_name_mapping')\
                        .insert(record)\
                        .execute()

                successful_updates += 1

            except Exception as e:
                failed_updates += 1
                logger.error(f"❌ Error processing '{record['school_name']}': {e}")

        logger.info("\n" + "=" * 80)
        logger.info("UPLOAD SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total records: {total_results}")
        logger.info(f"Successfully updated: {successful_updates}")
        logger.info(f"Failed updates: {failed_updates}")
        logger.info("=" * 80)

    def print_sample_matches(self, results: List[Dict], sample_size: int = 10):
        """Print sample matches for review"""
        logger.info("\n" + "=" * 80)
        logger.info("SAMPLE MATCHES (for verification)")
        logger.info("=" * 80)

        # Show some exact original matches
        exact_original = [r for r in results if r['match_type'] == 'exact_original']
        if exact_original:
            logger.info("\nExact Original Matches (no normalization needed):")
            for match in exact_original[:sample_size]:
                logger.info(f"  '{match['school_name']}' → '{match['team_name']}'")

        # Show some exact matches (normalized)
        exact = [r for r in results if r['match_type'] == 'exact']
        if exact:
            logger.info("\nExact Matches (normalized):")
            for match in exact[:sample_size]:
                logger.info(f"  '{match['school_name']}' → '{match['team_name']}'")

        # Show some fuzzy matches
        fuzzy = [r for r in results if r['match_type'] == 'fuzzy']
        if fuzzy:
            logger.info("\nFuzzy Matches (>90% confidence - NEEDS REVIEW):")
            for match in fuzzy[:sample_size]:
                conf = match['confidence_score'] * 100 if match['confidence_score'] else 0
                logger.info(f"  '{match['school_name']}' → '{match['team_name']}' ({conf:.1f}%)")

        # Show some no matches
        no_match = [r for r in results if r['match_type'] == 'no_match']
        if no_match:
            logger.info("\nNo Matches Found (NEEDS MANUAL REVIEW):")
            for match in no_match[:sample_size]:
                logger.info(f"  '{match['school_name']}' (normalized: '{match['normalized_school_name']}')")

        logger.info("=" * 80)


def main():
    """Main execution function"""
    try:
        matcher = SchoolNameMatcher()

        logger.info("\n" + "=" * 80)
        logger.info("SCHOOL NAME MATCHING - UPDATE MODE")
        logger.info("=" * 80)
        logger.info("This will:")
        logger.info("1. Only process schools with NULL team_name (unmatched)")
        logger.info("2. Check original name first, then normalized name, then fuzzy match")
        logger.info("3. UPDATE existing records in the database")
        logger.info("=" * 80)

        # Run matching algorithm (only unmatched schools)
        results = matcher.match_all_schools(only_unmatched=True)

        if not results:
            logger.info("\n✅ All schools already matched! No work to do.")
            return

        # Print sample matches for review
        matcher.print_sample_matches(results, sample_size=20)

        # Ask for confirmation before uploading
        logger.info("\n" + "=" * 80)
        response = input("\nDo you want to UPDATE these results in the database? (yes/no): ").strip().lower()

        if response in ['yes', 'y']:
            matcher.upload_to_database(results, use_update=True)
            logger.info("\n✅ Matching process completed successfully!")
            logger.info("\nNext steps:")
            logger.info("1. Review the updated matches in Supabase")
            logger.info("2. Manually verify fuzzy matches and no_matches")
            logger.info("3. Update the 'verified' column (true/false) for each record")
        else:
            logger.info("\nUpdate cancelled. Results not saved to database.")

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
