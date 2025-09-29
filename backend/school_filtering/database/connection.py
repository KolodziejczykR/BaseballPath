"""
Supabase database connection utilities for school filtering
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

from typing import Optional
from supabase import create_client, Client
from dotenv import load_dotenv

from ..exceptions import DatabaseConnectionError

load_dotenv()


class SupabaseConnection:
    """Singleton Supabase connection manager for school filtering operations"""

    _instance: Optional['SupabaseConnection'] = None
    _client: Optional[Client] = None

    def __new__(cls) -> 'SupabaseConnection':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:
            self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize Supabase client with environment variables"""
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")

        if not url or not key:
            raise DatabaseConnectionError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment variables"
            )

        try:
            self._client = create_client(url, key)
        except Exception as e:
            raise DatabaseConnectionError(f"Failed to create Supabase client: {str(e)}")

    @property
    def client(self) -> Client:
        """Get the Supabase client instance"""
        if self._client is None:
            raise DatabaseConnectionError("Supabase client not initialized")
        return self._client

    def test_connection(self) -> bool:
        """Test the database connection"""
        try:
            # Simple query to test connection
            response = self.client.table('school_data_expanded').select('count').limit(1).execute()
            return True
        except Exception:
            return False