"""
Async database queries for school filtering pipeline
"""

import os
import logging
from typing import List, Dict, Any
from supabase import create_client, Client
from backend.utils.school_group_constants import POWER_4_D1, NON_P4_D1, NON_D1

logger = logging.getLogger(__name__)


class AsyncSchoolDataQueries:
    """
    Simple async database query interface for school data from Supabase
    """

    def __init__(self):
        """Initialize the async database connection"""
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_KEY')

        if not supabase_url or not supabase_key:
            raise ValueError("Supabase credentials not found. Set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables.")

        self.client: Client = create_client(supabase_url, supabase_key)
        logger.info("AsyncSchoolDataQueries initialized with Supabase connection")

    async def health_check(self) -> Dict[str, Any]:
        """Check database health and connection"""
        try:
            # Simple query to check connection
            self.client.table('school_data_general').select('school_name').limit(1).execute()

            # Get total count for health check
            count_result = self.client.table('school_data_general').select('school_name', count='exact').execute()
            school_count = count_result.count if hasattr(count_result, 'count') else len(count_result.data)

            return {
                'status': 'healthy',
                'school_count': school_count,
                'connection': 'active'
            }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'status': 'unhealthy',
                'school_count': 0,
                'connection': 'failed',
                'error': str(e)
            }

    async def get_all_schools(self) -> List[Dict[str, Any]]:
        """Get all schools from the database"""
        try:
            result = self.client.table('school_data_general').select('*').execute()
            schools = result.data if result.data else []
            logger.info(f"Retrieved {len(schools)} schools from database")
            return schools
        except Exception as e:
            logger.error(f"Failed to retrieve all schools: {e}")
            return []

    async def get_schools_by_division_group(self, division_group: str) -> List[Dict[str, Any]]:
        """Get schools by division group"""
        try:
            # Validate division group
            valid_divisions = [POWER_4_D1, NON_P4_D1, NON_D1]
            if division_group not in valid_divisions:
                logger.warning(f"Invalid division group: {division_group}")
                return []

            result = self.client.table('school_data_general')\
                .select('*')\
                .eq('division_group', division_group)\
                .execute()

            schools = result.data if result.data else []
            logger.info(f"Retrieved {len(schools)} schools for division {division_group}")
            return schools
        except Exception as e:
            logger.error(f"Failed to retrieve schools for division {division_group}: {e}")
            return []

    async def get_schools_by_names(self, school_names: List[str]) -> List[Dict[str, Any]]:
        """Get schools by a list of school names (batch query)"""
        try:
            if not school_names:
                return []

            # Use 'in' filter for batch query
            result = self.client.table('school_data_general')\
                .select('*')\
                .in_('school_name', school_names)\
                .execute()

            schools = result.data if result.data else []
            logger.info(f"Batch retrieved {len(schools)} schools for {len(school_names)} names")
            return schools
        except Exception as e:
            logger.error(f"Failed to batch retrieve schools: {e}")
            return []

    async def get_schools_by_division_groups(self, division_groups: List[str]) -> List[Dict[str, Any]]:
        """Get schools by multiple division groups"""
        try:
            if not division_groups:
                return []

            # Validate all division groups
            valid_divisions = [POWER_4_D1, NON_P4_D1, NON_D1]
            invalid_divisions = [d for d in division_groups if d not in valid_divisions]
            if invalid_divisions:
                logger.warning(f"Invalid division groups: {invalid_divisions}")
                division_groups = [d for d in division_groups if d in valid_divisions]

            if not division_groups:
                return []

            result = self.client.table('school_data_general')\
                .select('*')\
                .in_('division_group', division_groups)\
                .execute()

            schools = result.data if result.data else []
            logger.info(f"Retrieved {len(schools)} schools for divisions {division_groups}")
            return schools
        except Exception as e:
            logger.error(f"Failed to retrieve schools for divisions {division_groups}: {e}")
            return []

    async def close(self):
        """Close database connection (no-op for Supabase)"""
        # Supabase client doesn't need explicit closing
        logger.debug("Database connection closed")
        pass