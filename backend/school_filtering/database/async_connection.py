"""
Async Supabase database connection utilities with connection pooling and retry logic
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

import asyncio
import logging
from typing import Optional, Any, Dict
from contextlib import asynccontextmanager
from supabase import create_client, Client
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import aiohttp
from asyncio_throttle import Throttler

from ..exceptions import DatabaseConnectionError

load_dotenv()
logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Simple circuit breaker implementation for database operations"""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN

    def call(self, func):
        """Decorator to wrap functions with circuit breaker logic"""
        async def wrapper(*args, **kwargs):
            if self.state == 'OPEN':
                if self._should_attempt_reset():
                    self.state = 'HALF_OPEN'
                else:
                    raise DatabaseConnectionError("Circuit breaker is OPEN - database unavailable")

            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result
            except Exception as e:
                self._on_failure()
                raise e

        return wrapper

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True
        return (asyncio.get_event_loop().time() - self.last_failure_time) >= self.recovery_timeout

    def _on_success(self):
        """Reset circuit breaker on successful operation"""
        self.failure_count = 0
        self.state = 'CLOSED'

    def _on_failure(self):
        """Record failure and potentially open circuit"""
        self.failure_count += 1
        self.last_failure_time = asyncio.get_event_loop().time()

        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")


class AsyncSupabaseConnection:
    """Async Supabase connection manager with connection pooling and resilience"""

    _instance: Optional['AsyncSupabaseConnection'] = None
    _client: Optional[Client] = None
    _session: Optional[aiohttp.ClientSession] = None
    _throttler: Optional[Throttler] = None
    _circuit_breaker: Optional[CircuitBreaker] = None
    _connection_semaphore: Optional[asyncio.Semaphore] = None

    def __new__(cls) -> 'AsyncSupabaseConnection':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, max_connections: int = 10, requests_per_second: int = 50):
        if self._client is None:
            self.max_connections = max_connections
            self.requests_per_second = requests_per_second
            self._initialize_components()

    def _initialize_components(self) -> None:
        """Initialize all async components"""
        try:
            # Initialize Supabase client
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_SERVICE_KEY")

            if not url or not key:
                raise DatabaseConnectionError(
                    "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment variables"
                )

            # Create Supabase client
            self._client = create_client(url, key)

            # Initialize connection controls
            self._connection_semaphore = asyncio.Semaphore(self.max_connections)
            self._throttler = Throttler(rate_limit=self.requests_per_second, period=1.0)
            self._circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)

            logger.info(f"Async Supabase connection initialized with {self.max_connections} max connections")

        except Exception as e:
            raise DatabaseConnectionError(f"Failed to initialize async Supabase client: {str(e)}")

    @property
    def client(self) -> Client:
        """Get the Supabase client instance"""
        if self._client is None:
            raise DatabaseConnectionError("Async Supabase client not initialized")
        return self._client

    @asynccontextmanager
    async def get_connection(self):
        """Context manager for acquiring database connections with throttling"""
        async with self._connection_semaphore:
            async with self._throttler:
                try:
                    yield self._client
                except Exception as e:
                    logger.error(f"Database operation failed: {e}")
                    raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError))
    )
    async def execute_with_retry(self, operation_func, *args, **kwargs):
        """Execute database operation with retry logic"""
        async with self.get_connection() as client:
            try:
                # Use circuit breaker for the operation
                wrapped_func = self._circuit_breaker.call(operation_func)
                return await wrapped_func(client, *args, **kwargs)
            except Exception as e:
                logger.error(f"Database operation failed: {e}")
                raise DatabaseConnectionError(f"Failed database operation: {str(e)}")

    async def test_connection(self) -> bool:
        """Test the database connection"""
        try:
            async def _test_query(client):
                # Convert sync operation to async-like operation
                response = client.table('school_data_expanded').select('count').limit(1).execute()
                return response.data is not None

            result = await self.execute_with_retry(_test_query)
            return result
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        return {
            'max_connections': self.max_connections,
            'available_connections': self._connection_semaphore._value,
            'active_connections': self.max_connections - self._connection_semaphore._value,
            'circuit_breaker_state': self._circuit_breaker.state,
            'failure_count': self._circuit_breaker.failure_count,
            'requests_per_second_limit': self.requests_per_second
        }

    async def close(self):
        """Clean up resources"""
        if self._session and not self._session.closed:
            await self._session.close()

        # Reset singleton state for clean shutdown
        AsyncSupabaseConnection._instance = None
        AsyncSupabaseConnection._client = None
        AsyncSupabaseConnection._session = None
        AsyncSupabaseConnection._throttler = None
        AsyncSupabaseConnection._circuit_breaker = None
        AsyncSupabaseConnection._connection_semaphore = None

        logger.info("Async Supabase connection closed")


# Global instance for dependency injection
async_db_connection = AsyncSupabaseConnection()