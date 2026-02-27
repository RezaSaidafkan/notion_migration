import unittest
from unittest.mock import patch
import pytest
import sys


@pytest.fixture(scope="function")
def mock_async(request):
    with patch("common_libs.singletons.rate_limiter_singleton.AsyncLimiter") as mocked_async_limiter:
        from common_libs.singletons.rate_limiter_singleton import RateLimiter, RateLimiterExeption
        if hasattr(RateLimiter, '_singleton') and RateLimiter._singleton:
            RateLimiter._singleton = None
            if hasattr(RateLimiter._singleton, '_initialized'):
                del RateLimiter._initialized
                del RateLimiter._rate_limiter

        if request.instance:
            request.instance.RateLimiter = RateLimiter
            request.instance.RateLimiterExeption = RateLimiterExeption
            request.instance.mocked_async_limiter = mocked_async_limiter
    yield
    
    
@pytest.mark.usefixtures("mock_async")
class SingletonTestRateLimited(unittest.IsolatedAsyncioTestCase):
        
    def test_singleton(self):
        """Validate only a single instance created throught multiple calls."""
        # Arrange
        kwargs1 = {"time_period": 1, "max_rate": 3}
        kwargs2 = {"time_period": 2, "max_rate": 3}
        
        # Act
        singleton_1 = self.RateLimiter(**kwargs1)
        singleton_2 = self.RateLimiter(**kwargs2)

        # Assert
        assert singleton_1 == singleton_2
        del singleton_1
        del singleton_2

    def test_not_passing_arg(self):
        """Validate the class decorator raises when required args & kwargs are not passed."""
        # Arrange & Act & Assert
        self.assertRaises(self.RateLimiterExeption, self.RateLimiter)
            
    
    