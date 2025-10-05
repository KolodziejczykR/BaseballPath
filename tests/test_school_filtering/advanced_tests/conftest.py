"""
Advanced test fixtures for production testing
"""

import pytest
import os
import time
import psutil
import threading
import asyncio
from typing import Dict, List, Any
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
from dotenv import load_dotenv

# Load environment variables from .env file in test_school_filtering directory
test_dir = os.path.dirname(os.path.dirname(__file__))
env_path = os.path.join(test_dir, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

from backend.utils.preferences_types import UserPreferences
from backend.utils.prediction_types import MLPipelineResults, D1PredictionResult, P4PredictionResult
from backend.utils.player_types import PlayerInfielder




@pytest.fixture
def real_database_available():
    """Check if real Supabase credentials are available"""
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
    return bool(supabase_url and supabase_key)


@pytest.fixture
def performance_tracker():
    """Track performance metrics during tests"""
    class PerformanceTracker:
        def __init__(self):
            self.start_time = None
            self.end_time = None
            self.memory_start = None
            self.memory_end = None
            self.process = psutil.Process()

        def start(self):
            self.start_time = time.time()
            self.memory_start = self.process.memory_info().rss / 1024 / 1024  # MB

        def stop(self):
            self.end_time = time.time()
            self.memory_end = self.process.memory_info().rss / 1024 / 1024  # MB

        @property
        def duration(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None

        @property
        def memory_used(self):
            if self.memory_start and self.memory_end:
                return self.memory_end - self.memory_start
            return None

        @property
        def memory_peak(self):
            return self.process.memory_info().rss / 1024 / 1024  # MB

    return PerformanceTracker()


@pytest.fixture
def load_test_users():
    """Generate multiple user configurations for load testing"""
    users = []

    # Generate 30 different user scenarios
    states = ['CA', 'TX', 'FL', 'NY', 'PA', 'OH']
    budgets = [20000, 30000, 40000, 50000, 60000]
    academic_ratings = ['B', 'B+', 'A-', 'A']

    for i in range(30):
        user_prefs = UserPreferences(
            user_state=states[i % len(states)],
            max_budget=budgets[i % len(budgets)],
            min_academic_rating=academic_ratings[i % len(academic_ratings)],
            preferred_states=[states[i % len(states)], states[(i+1) % len(states)]],
            gpa=3.0 + (i % 10) * 0.1,
            sat=1200 + (i % 5) * 50
        )

        # Create ML results
        player = PlayerInfielder(
            height=70 + (i % 4), weight=170 + (i % 20),
            exit_velo_max=85 + (i % 10), sixty_time=6.8 + (i % 8) * 0.1,
            throwing_hand='R' if i % 2 == 0 else 'L',
            hitting_handedness='R' if i % 3 == 0 else 'L',
            region=states[i % len(states)], primary_position='SS', inf_velo=75 + (i % 10)
        )

        d1_prob = 0.3 + (i % 7) * 0.1
        p4_prob = 0.2 + (i % 5) * 0.1

        ml_results = MLPipelineResults(
            player=player,
            d1_results=D1PredictionResult(
                d1_probability=d1_prob,
                d1_prediction=d1_prob > 0.5,
                confidence='Medium',
                model_version='v2.1'
            ),
            p4_results=P4PredictionResult(
                p4_probability=p4_prob,
                p4_prediction=p4_prob > 0.5,
                confidence='Medium',
                is_elite=p4_prob > 0.7,
                model_version='v1.3'
            )
        )

        users.append({
            'user_id': f'user_{i}',
            'preferences': user_prefs,
            'ml_results': ml_results
        })

    return users


@pytest.fixture
def bad_school_data():
    """Generate various types of malformed school data"""
    return [
        # Missing required fields
        {
            'school_name': None,
            'school_state': 'CA',
            'division_group': 'Non-D1'
        },

        # Invalid data types
        {
            'school_name': 'Invalid School',
            'school_state': 'CA',
            'division_group': 'Non-D1',
            'undergrad_enrollment': 'not_a_number',
            'academics_grade': 123,
            'avg_sat': 'invalid_sat'
        },

        # Out of range values
        {
            'school_name': 'Out of Range School',
            'school_state': 'INVALID_STATE',
            'division_group': 'Non-D1',
            'undergrad_enrollment': -5000,
            'avg_sat': 3000,  # SAT max is 1600
            'avg_gpa': 5.5,   # GPA max is 4.0
            'admission_rate': 1.5  # Rate should be 0-1
        },

        # Missing critical financial data
        {
            'school_name': 'No Financial Data',
            'school_state': 'CA',
            'division_group': 'Non-D1',
            'in_state_tuition': None,
            'out_of_state_tuition': None
        },

        # Unicode and special characters
        {
            'school_name': 'École Spéciale & University™',
            'school_state': 'CA',
            'division_group': 'Non-D1',
            'special_chars': '🏫📚💰'
        },

        # Empty/whitespace values
        {
            'school_name': '   ',
            'school_state': '',
            'division_group': 'Non-D1'
        },

        # Inconsistent data
        {
            'school_name': 'Inconsistent School',
            'school_state': 'CA',
            'division_group': 'Power 4 D1',
            'athletics_grade': 'F',  # Contradictory - Power 4 with F athletics
            'academics_grade': 'A+',
            'undergrad_enrollment': 100  # Too small for Power 4
        }
    ]


@pytest.fixture
def concurrent_executor():
    """Thread pool executor for load testing"""
    with ThreadPoolExecutor(max_workers=35) as executor:
        yield executor


@pytest.fixture
def memory_monitor():
    """Monitor memory usage during tests"""
    class MemoryMonitor:
        def __init__(self):
            self.process = psutil.Process()
            self.baseline = self.process.memory_info().rss / 1024 / 1024
            self.peak = self.baseline
            self.monitoring = False
            self.monitor_thread = None

        def start_monitoring(self):
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor)
            self.monitor_thread.start()

        def stop_monitoring(self):
            self.monitoring = False
            if self.monitor_thread:
                self.monitor_thread.join()

        def _monitor(self):
            while self.monitoring:
                current = self.process.memory_info().rss / 1024 / 1024
                if current > self.peak:
                    self.peak = current
                time.sleep(0.1)

        @property
        def current_usage(self):
            return self.process.memory_info().rss / 1024 / 1024

        @property
        def memory_increase(self):
            return self.peak - self.baseline

    return MemoryMonitor()


@pytest.fixture
def query_timer():
    """Time database queries for optimization testing"""
    class QueryTimer:
        def __init__(self):
            self.queries = []

        def time_query(self, query_name, query_func, *args, **kwargs):
            import asyncio
            import inspect

            start_time = time.time()
            try:
                # Check if the function is a coroutine function
                if inspect.iscoroutinefunction(query_func):
                    # Use asyncio.run for async functions
                    result = asyncio.run(query_func(*args, **kwargs))
                else:
                    result = query_func(*args, **kwargs)

                success = True
                error = None
            except Exception as e:
                result = None
                success = False
                error = str(e)

            end_time = time.time()
            duration = end_time - start_time

            self.queries.append({
                'name': query_name,
                'duration': duration,
                'success': success,
                'error': error,
                'result_size': len(result) if isinstance(result, (list, dict)) else None
            })

            return result, duration, success

        async def time_query_async(self, query_name, query_func, *args, **kwargs):
            """Async version of time_query for use within async test methods"""
            import inspect

            start_time = time.time()
            try:
                # Check if the function is a coroutine function
                if inspect.iscoroutinefunction(query_func):
                    result = await query_func(*args, **kwargs)
                else:
                    result = query_func(*args, **kwargs)

                success = True
                error = None
            except Exception as e:
                result = None
                success = False
                error = str(e)

            end_time = time.time()
            duration = end_time - start_time

            self.queries.append({
                'name': query_name,
                'duration': duration,
                'success': success,
                'error': error,
                'result_size': len(result) if isinstance(result, (list, dict)) else None
            })

            return result, duration, success

        def get_stats(self):
            if not self.queries:
                return {}

            durations = [q['duration'] for q in self.queries if q['success']]
            return {
                'total_queries': len(self.queries),
                'successful_queries': sum(1 for q in self.queries if q['success']),
                'failed_queries': sum(1 for q in self.queries if not q['success']),
                'avg_duration': sum(durations) / len(durations) if durations else 0,
                'max_duration': max(durations) if durations else 0,
                'min_duration': min(durations) if durations else 0,
                'queries': self.queries
            }

    return QueryTimer()


@pytest.fixture
def realistic_preferences():
    """Generate realistic user preference scenarios"""
    scenarios = [
        # Budget-conscious student
        {
            'name': 'budget_conscious',
            'preferences': UserPreferences(
                user_state='CA',
                max_budget=25000,
                min_academic_rating='B',
                preferred_states=['CA', 'NV', 'AZ'],
                gpa=3.2,
                sat=1200
            )
        },

        # High achiever
        {
            'name': 'high_achiever',
            'preferences': UserPreferences(
                user_state='NY',
                max_budget=60000,
                min_academic_rating='A-',
                min_athletics_rating='A-',
                preferred_states=['NY', 'CT', 'MA'],
                gpa=3.8,
                sat=1450
            )
        },

        # Out-of-state seeker
        {
            'name': 'out_of_state',
            'preferences': UserPreferences(
                user_state='TX',
                max_budget=45000,
                min_academic_rating='B+',
                preferred_states=['CA', 'FL', 'NC'],  # Not including TX
                gpa=3.5,
                sat=1350
            )
        },

        # Specific requirements
        {
            'name': 'specific_requirements',
            'preferences': UserPreferences(
                user_state='FL',
                max_budget=35000,
                min_academic_rating='B+',
                min_athletics_rating='B',
                preferred_school_size=['Medium'],
                party_scene_preference=['Moderate'],
                gpa=3.4,
                sat=1300
            )
        }
    ]

    return scenarios