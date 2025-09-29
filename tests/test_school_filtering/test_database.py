"""
Tests for database connection and queries
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

import pytest
from unittest.mock import Mock, patch, MagicMock

from backend.school_filtering.database import SupabaseConnection, SchoolDataQueries
from backend.school_filtering.exceptions import DatabaseConnectionError, SchoolDataError


class TestSupabaseConnection:
    """Test cases for SupabaseConnection"""

    def setup_method(self):
        # Reset singleton instance for testing
        SupabaseConnection._instance = None
        SupabaseConnection._client = None

    @patch.dict('os.environ', {'SUPABASE_URL': 'test_url', 'SUPABASE_SERVICE_KEY': 'test_key'})
    @patch('backend.school_filtering.database.connection.create_client')
    def test_connection_initialization(self, mock_create_client):
        """Test connection initializes correctly"""
        mock_client = Mock()
        mock_create_client.return_value = mock_client

        connection = SupabaseConnection()

        assert connection.client == mock_client
        mock_create_client.assert_called_once_with('test_url', 'test_key')

    def test_connection_missing_env_vars(self):
        """Test connection fails with missing environment variables"""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(DatabaseConnectionError):
                SupabaseConnection()

    @patch.dict('os.environ', {'SUPABASE_URL': 'test_url', 'SUPABASE_SERVICE_KEY': 'test_key'})
    @patch('backend.school_filtering.database.connection.create_client')
    def test_singleton_behavior(self, mock_create_client):
        """Test that SupabaseConnection follows singleton pattern"""
        mock_client = Mock()
        mock_create_client.return_value = mock_client

        connection1 = SupabaseConnection()
        connection2 = SupabaseConnection()

        assert connection1 is connection2
        assert mock_create_client.call_count == 1

    @patch.dict('os.environ', {'SUPABASE_URL': 'test_url', 'SUPABASE_SERVICE_KEY': 'test_key'})
    @patch('backend.school_filtering.database.connection.create_client')
    def test_connection_test(self, mock_create_client):
        """Test connection testing functionality"""
        mock_client = Mock()
        mock_table = Mock()
        mock_select = Mock()
        mock_limit = Mock()
        mock_execute = Mock()

        mock_execute.execute.return_value = Mock(data=[])
        mock_limit.limit.return_value = mock_execute
        mock_select.select.return_value = mock_limit
        mock_table.table.return_value = mock_select
        mock_client.table.return_value = mock_table
        mock_create_client.return_value = mock_client

        connection = SupabaseConnection()
        result = connection.test_connection()

        assert result is True


class TestSchoolDataQueries:
    """Test cases for SchoolDataQueries"""

    def setup_method(self):
        with patch('backend.school_filtering.database.queries.SupabaseConnection'):
            self.queries = SchoolDataQueries()

    @patch('backend.school_filtering.database.queries.SupabaseConnection')
    def test_get_all_schools_success(self, mock_connection):
        """Test successful retrieval of all schools"""
        mock_client = Mock()
        mock_connection.return_value.client = mock_client

        # Mock the chain of method calls
        mock_response = Mock()
        mock_response.data = [
            {'school_name': 'Test University', 'state': 'CA'},
            {'school_name': 'Another College', 'state': 'NY'}
        ]

        mock_client.table.return_value.select.return_value.execute.return_value = mock_response

        result = self.queries.get_all_schools()

        assert len(result) == 2
        assert result[0]['school_name'] == 'Test University'
        mock_client.table.assert_called_with('school_data_expanded')

    @patch('backend.school_filtering.database.queries.SupabaseConnection')
    def test_get_all_schools_empty(self, mock_connection):
        """Test retrieval when no schools exist"""
        mock_client = Mock()
        mock_connection.return_value.client = mock_client

        mock_response = Mock()
        mock_response.data = None

        mock_client.table.return_value.select.return_value.execute.return_value = mock_response

        result = self.queries.get_all_schools()
        assert result == []

    @patch('backend.school_filtering.database.queries.SupabaseConnection')
    def test_get_all_schools_error(self, mock_connection):
        """Test error handling in get_all_schools"""
        mock_client = Mock()
        mock_connection.return_value.client = mock_client

        mock_client.table.side_effect = Exception("Database error")

        with pytest.raises(SchoolDataError):
            self.queries.get_all_schools()

    @patch('backend.school_filtering.database.queries.SupabaseConnection')
    def test_get_schools_by_names(self, mock_connection):
        """Test retrieval of schools by names"""
        mock_client = Mock()
        mock_connection.return_value.client = mock_client

        mock_response = Mock()
        mock_response.data = [{'school_name': 'Test University'}]

        mock_client.table.return_value.select.return_value.in_.return_value.execute.return_value = mock_response

        result = self.queries.get_schools_by_names(['Test University'])

        assert len(result) == 1
        assert result[0]['school_name'] == 'Test University'

    @patch('backend.school_filtering.database.queries.SupabaseConnection')
    def test_get_schools_by_names_empty_list(self, mock_connection):
        """Test get_schools_by_names with empty list"""
        result = self.queries.get_schools_by_names([])
        assert result == []

    @patch('backend.school_filtering.database.queries.SupabaseConnection')
    def test_get_schools_with_filters(self, mock_connection):
        """Test retrieval with database-level filters"""
        mock_client = Mock()
        mock_connection.return_value.client = mock_connection
        mock_connection.client = mock_client

        mock_query = Mock()
        mock_client.table.return_value.select.return_value = mock_query

        mock_response = Mock()
        mock_response.data = [{'school_name': 'Filtered School'}]
        mock_query.eq.return_value.execute.return_value = mock_response

        filters = {'state': 'CA'}
        result = self.queries.get_schools_with_filters(filters)

        assert len(result) == 1
        mock_query.eq.assert_called_with('state', 'CA')

    @patch('backend.school_filtering.database.queries.SupabaseConnection')
    def test_get_school_count(self, mock_connection):
        """Test getting school count"""
        mock_client = Mock()
        mock_connection.return_value.client = mock_client

        mock_response = Mock()
        mock_response.count = 150

        mock_client.table.return_value.select.return_value.limit.return_value.execute.return_value = mock_response

        result = self.queries.get_school_count()
        assert result == 150

    @patch('backend.school_filtering.database.queries.SupabaseConnection')
    def test_get_available_columns(self, mock_connection):
        """Test getting available columns"""
        mock_client = Mock()
        mock_connection.return_value.client = mock_client

        mock_response = Mock()
        mock_response.data = [{'school_name': 'Test', 'state': 'CA', 'enrollment': 5000}]

        mock_client.table.return_value.select.return_value.limit.return_value.execute.return_value = mock_response

        result = self.queries.get_available_columns()
        expected_columns = ['school_name', 'state', 'enrollment']
        assert result == expected_columns