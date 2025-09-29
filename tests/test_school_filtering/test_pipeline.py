"""
Tests for the main school filtering pipeline
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

import pytest
from unittest.mock import Mock, patch
from typing import List, Dict, Any

from backend.utils.preferences_types import UserPreferences
from backend.utils.prediction_types import MLPipelineResults, D1PredictionResult, P4PredictionResult
from backend.utils.school_group_constants import POWER_4_D1, NON_P4_D1, NON_D1
from backend.school_filtering.pipeline import SchoolFilteringPipeline, filter_schools_for_llm
from backend.school_filtering.exceptions import FilteringError, InvalidPreferencesError


class TestSchoolFilteringPipeline:
    """Test cases for SchoolFilteringPipeline"""

    def setup_method(self):
        """Set up test fixtures"""
        self.pipeline = SchoolFilteringPipeline()

    def test_pipeline_initialization(self):
        """Test pipeline initializes correctly"""
        assert self.pipeline is not None
        assert len(self.pipeline.filters) == 5
        assert self.pipeline.filter_results == []

    @patch('backend.school_filtering.pipeline.SchoolDataQueries')
    def test_filter_schools_success(self, mock_queries):
        """Test successful school filtering"""
        # Mock database response
        mock_schools = [
            {
                'school_name': 'Test University',
                'state': 'CA',
                'academics_grade': 'A-',
                'athletics_grade': 'B+',
                'out_of_state_tuition': 20000,
                'undergrad_enrollment': 5000
            },
            {
                'school_name': 'Another College',
                'state': 'NY',
                'academics_grade': 'B+',
                'athletics_grade': 'A',
                'out_of_state_tuition': 35000,
                'undergrad_enrollment': 15000
            }
        ]
        mock_queries.return_value.get_all_schools.return_value = mock_schools

        # Create test preferences
        preferences = UserPreferences(
            max_budget=25000,
            min_academic_rating='B+',
            preferred_states=['CA', 'NY']
        )

        result = self.pipeline.filter_schools(preferences)

        assert isinstance(result, list)
        assert len(result) <= len(mock_schools)

    def test_filter_schools_invalid_preferences(self):
        """Test filtering with invalid preferences"""
        with pytest.raises(InvalidPreferencesError):
            self.pipeline.filter_schools("invalid_preferences")

    @patch('backend.school_filtering.pipeline.SchoolDataQueries')
    def test_filter_schools_empty_database(self, mock_queries):
        """Test filtering with empty database"""
        mock_queries.return_value.get_all_schools.return_value = []

        preferences = UserPreferences(max_budget=25000)
        result = self.pipeline.filter_schools(preferences)

        assert result == []

    @patch('backend.school_filtering.pipeline.SchoolDataQueries')
    def test_filter_schools_with_ml_results(self, mock_queries):
        """Test filtering with ML pipeline results"""
        mock_schools = [
            {
                'school_name': 'D1 University',
                'state': 'CA',
                'academics_grade': 'A-',
                'athletics_grade': 'A',
                'division': 'D1',
                'out_of_state_tuition': 20000
            },
            {
                'school_name': 'D2 College',
                'state': 'CA',
                'academics_grade': 'B+',
                'athletics_grade': 'B',
                'division': 'D2',
                'out_of_state_tuition': 15000
            }
        ]
        mock_queries.return_value.get_all_schools.return_value = mock_schools

        preferences = UserPreferences(max_budget=25000)

        # Create mock ML results for D1 player
        mock_player = Mock()
        d1_results = D1PredictionResult(
            d1_probability=0.8,
            d1_prediction=True,
            confidence='High',
            model_version='v2.1'
        )
        ml_results = MLPipelineResults(
            player=mock_player,
            d1_results=d1_results,
            p4_results=None
        )

        result = self.pipeline.filter_schools(preferences, ml_results)
        assert isinstance(result, list)
        # Should include D1 schools for D1-predicted player
        assert 'D1 University' in result

    def test_get_filtering_summary(self):
        """Test filtering summary generation"""
        summary = self.pipeline.get_filtering_summary()

        assert isinstance(summary, dict)
        assert 'total_filters_applied' in summary
        assert 'filters' in summary
        assert isinstance(summary['filters'], list)

    def test_convenience_function(self):
        """Test convenience function"""
        with patch('backend.school_filtering.pipeline.SchoolFilteringPipeline') as mock_pipeline:
            mock_instance = Mock()
            mock_instance.filter_schools.return_value = ['School 1', 'School 2']
            mock_pipeline.return_value = mock_instance

            preferences = UserPreferences(max_budget=25000)
            result = filter_schools_for_llm(preferences)

            assert result == ['School 1', 'School 2']
            mock_instance.filter_schools.assert_called_once_with(preferences, None)

    def test_ml_prediction_matching_power_4(self):
        """Test ML prediction matching for Power 4 players"""
        mock_player = Mock()
        d1_results = D1PredictionResult(
            d1_probability=0.9,
            d1_prediction=True,
            confidence='High',
            model_version='v2.1'
        )
        p4_results = P4PredictionResult(
            p4_probability=0.7,
            p4_prediction=True,
            confidence='High',
            is_elite=True,
            model_version='v1.3'
        )
        ml_results = MLPipelineResults(
            player=mock_player,
            d1_results=d1_results,
            p4_results=p4_results
        )

        # Test Power 4 school matching
        power4_school = {
            'school_name': 'Top University',
            'division': 'D1',
            'athletics_grade': 'A+'
        }

        assert self.pipeline._school_matches_ml_prediction(power4_school, ml_results)

        # Test that lower-tier schools don't match Power 4 prediction
        d2_school = {
            'school_name': 'D2 College',
            'division': 'D2',
            'athletics_grade': 'B'
        }

        assert not self.pipeline._school_matches_ml_prediction(d2_school, ml_results)

    def test_ml_prediction_matching_non_d1(self):
        """Test ML prediction matching for Non-D1 players"""
        mock_player = Mock()
        d1_results = D1PredictionResult(
            d1_probability=0.2,
            d1_prediction=False,
            confidence='High',
            model_version='v2.1'
        )
        ml_results = MLPipelineResults(
            player=mock_player,
            d1_results=d1_results,
            p4_results=None
        )

        # Test D2/D3 school matching
        d2_school = {
            'school_name': 'D2 College',
            'division': 'D2',
            'athletics_grade': 'B'
        }

        assert self.pipeline._school_matches_ml_prediction(d2_school, ml_results)

        # Test that top D1 schools don't match Non-D1 prediction
        elite_d1_school = {
            'school_name': 'Elite University',
            'division': 'D1',
            'athletics_grade': 'A+'
        }

        assert not self.pipeline._school_matches_ml_prediction(elite_d1_school, ml_results)