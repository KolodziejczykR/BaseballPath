"""
School Name Resolver
Resolves names between school_data_general and baseball_rankings_data using the mapping table
"""

import os
import sys
import logging
from typing import Optional, Dict
from functools import lru_cache

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class SchoolNameResolver:
    """
    Resolves school names to team names and vice versa using the mapping table
    Uses caching to minimize database queries
    """

    def __init__(self):
        """Initialize Supabase client and load mappings"""
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")

        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

        self.supabase: Client = create_client(url, key)
        self._mapping_cache = {}  # Cache for school_name -> team_name
        self._reverse_cache = {}  # Cache for team_name -> school_name
        self._cache_loaded = False

    @staticmethod
    def _normalize_name(name: Optional[str]) -> str:
        if not isinstance(name, str):
            return ""
        return " ".join(name.strip().lower().split())

    def _load_cache(self):
        """Load mappings into cache, preferring verified rows and falling back when needed."""
        if self._cache_loaded:
            return

        try:
            logger.info("Loading school name mappings into cache...")

            response = self.supabase.table('school_baseball_ranking_name_mapping')\
                .select('school_name, team_name')\
                .eq('verified', True)\
                .not_.is_('team_name', 'null')\
                .execute()
            mapping_rows = response.data or []

            if not mapping_rows:
                logger.warning("No verified mappings found; falling back to non-false mappings")
                fallback_response = self.supabase.table('school_baseball_ranking_name_mapping')\
                    .select('school_name, team_name')\
                    .neq('verified', False)\
                    .not_.is_('team_name', 'null')\
                    .execute()
                mapping_rows = fallback_response.data or []

            if not mapping_rows:
                logger.warning("No non-false mappings found; falling back to any non-null team_name mapping")
                fallback_any_response = self.supabase.table('school_baseball_ranking_name_mapping')\
                    .select('school_name, team_name')\
                    .not_.is_('team_name', 'null')\
                    .execute()
                mapping_rows = fallback_any_response.data or []

            if mapping_rows:
                for row in mapping_rows:
                    school_name = row['school_name']
                    team_name = row['team_name']
                    self._mapping_cache[school_name] = team_name
                    normalized_name = self._normalize_name(school_name)
                    if normalized_name:
                        self._mapping_cache[normalized_name] = team_name
                    self._reverse_cache[team_name] = school_name

                logger.info(f"✅ Loaded {len(mapping_rows)} mappings into cache")
            else:
                logger.warning("No school/team mappings found in database")

            self._cache_loaded = True

        except Exception as e:
            logger.error(f"❌ Error loading mappings cache: {e}")
            self._cache_loaded = True  # Mark as loaded to prevent repeated failures

    def get_team_name(self, school_name: str, verified_only: bool = True) -> Optional[str]:
        """
        Get team name from school name

        Args:
            school_name: School name from school_data_general (e.g., "Stanford University, Stanford, CA")
            verified_only: If True, only return verified mappings

        Returns:
            Team name from baseball_rankings_data (e.g., "Stanford") or None if not found
        """
        # Load cache if not already loaded
        if not self._cache_loaded:
            self._load_cache()

        # Check cache first
        if school_name in self._mapping_cache:
            return self._mapping_cache[school_name]

        normalized_name = self._normalize_name(school_name)
        if normalized_name in self._mapping_cache:
            return self._mapping_cache[normalized_name]

        # If not in cache and we want verified only, return None
        if verified_only:
            return None

        # Otherwise, query database for unverified mappings
        try:
            response = self.supabase.table('school_baseball_ranking_name_mapping')\
                .select('team_name')\
                .eq('school_name', school_name)\
                .not_.is_('team_name', 'null')\
                .limit(1)\
                .execute()

            if response.data and len(response.data) > 0:
                team_name = response.data[0]['team_name']
                logger.debug(f"Found unverified mapping: '{school_name}' → '{team_name}'")
                return team_name

        except Exception as e:
            logger.error(f"Error looking up team name for '{school_name}': {e}")

        return None

    def get_school_name(self, team_name: str, verified_only: bool = True) -> Optional[str]:
        """
        Get school name from team name (reverse lookup)

        Args:
            team_name: Team name from baseball_rankings_data (e.g., "Stanford")
            verified_only: If True, only return verified mappings

        Returns:
            School name from school_data_general (e.g., "Stanford University, Stanford, CA") or None
        """
        # Load cache if not already loaded
        if not self._cache_loaded:
            self._load_cache()

        # Check cache first
        if team_name in self._reverse_cache:
            return self._reverse_cache[team_name]

        # If not in cache and we want verified only, return None
        if verified_only:
            return None

        # Otherwise, query database for unverified mappings
        try:
            response = self.supabase.table('school_baseball_ranking_name_mapping')\
                .select('school_name')\
                .eq('team_name', team_name)\
                .limit(1)\
                .execute()

            if response.data and len(response.data) > 0:
                school_name = response.data[0]['school_name']
                logger.debug(f"Found unverified mapping: '{team_name}' → '{school_name}'")
                return school_name

        except Exception as e:
            logger.error(f"Error looking up school name for '{team_name}': {e}")

        return None

    def get_mapping_info(self, school_name: str) -> Optional[Dict]:
        """
        Get full mapping info for a school

        Args:
            school_name: School name from school_data_general

        Returns:
            Dictionary with mapping details or None
        """
        try:
            response = self.supabase.table('school_baseball_ranking_name_mapping')\
                .select('*')\
                .eq('school_name', school_name)\
                .limit(1)\
                .execute()

            if response.data and len(response.data) > 0:
                return response.data[0]

        except Exception as e:
            logger.error(f"Error getting mapping info for '{school_name}': {e}")

        return None

    def has_baseball_data(self, school_name: str) -> bool:
        """
        Check if a school has baseball rankings data available

        Args:
            school_name: School name from school_data_general

        Returns:
            True if team_name mapping exists, False otherwise
        """
        team_name = self.get_team_name(school_name, verified_only=False)
        return team_name is not None

    def reload_cache(self):
        """Force reload of the cache (useful after updates)"""
        self._mapping_cache = {}
        self._reverse_cache = {}
        self._cache_loaded = False
        self._load_cache()

    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        if not self._cache_loaded:
            self._load_cache()

        return {
            'verified_mappings': len(self._mapping_cache),
            'cache_loaded': self._cache_loaded
        }


# Global singleton instance
_resolver_instance = None

def get_resolver() -> SchoolNameResolver:
    """Get or create global resolver instance"""
    global _resolver_instance
    if _resolver_instance is None:
        _resolver_instance = SchoolNameResolver()
    return _resolver_instance
