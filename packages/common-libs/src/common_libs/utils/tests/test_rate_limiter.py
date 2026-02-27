# pylint: disable=all
import unittest
from unittest.mock import AsyncMock, call, patch
import pytest
import sys
from time import time


@pytest.fixture(scope="function")
def simulate_rate_limiting(request):
    from common_libs.singletons.rate_limiter_singleton import RateLimiter
    if hasattr(RateLimiter, '_singleton') and RateLimiter._singleton:
        RateLimiter._singleton = None
        if hasattr(RateLimiter._singleton, '_initialized'):
            del RateLimiter._initialized
            del RateLimiter._rate_limiter

    RateLimiter(2, 1)
    
    from common_libs.utils.rate_limiter import rate_limited
    @rate_limited
    async def rate_limited_api():
        pass

    async def rate_limited_caller(repetition):
        start = time()
        
        for _ in range(0, repetition):
            await rate_limited_api()
        return time() - start
    
    if request.instance:
        request.instance.rate_limited_caller = rate_limited_caller
    yield
 
 
@pytest.fixture(scope="function")
def apply_patching_singleton(request):
    with patch("common_libs.singletons.rate_limiter_singleton.AsyncLimiter") as mocked_async_limiter:
        from common_libs.singletons.rate_limiter_singleton import RateLimiter
        if hasattr(RateLimiter, '_singleton') and RateLimiter._singleton:
            RateLimiter._singleton = None
            if hasattr(RateLimiter._singleton, '_initialized'):
                del RateLimiter._initialized
                del RateLimiter._rate_limiter
        kwargs = {"time_period": 1, "max_rate": 3}
        rate_limiter_instance = RateLimiter(**kwargs)
        from common_libs.utils.rate_limiter import rate_limited
        if request.instance:
            request.instance.mocked_async_limiter = mocked_async_limiter
            request.instance.rate_limited = rate_limited
        yield
    del rate_limiter_instance
    if "RateLimiter" in sys.modules:
        del sys.modules["RateLimiter"]
    if "rate_limited" in sys.modules:
        del sys.modules["rate_limited"]
        
    
@pytest.mark.usefixtures("apply_patching_singleton")
class TestRateLimited(unittest.IsolatedAsyncioTestCase):
    def test_passing_correct_args(self):
        """Validate the class decorator passes when required args & kwargs are passed."""
        # Arrange, Act & Assert
        self.assertRaises(TypeError, self.rate_limited)

    async def test_wrapper_called_once(self):
        """Validate the wrapper is rate limiting the coroutine alongside all the args."""
        # Arrange
        coroutineArgs = "arg1"
        coroutineKwargs = {"some kwarg": "some value"}
        mockedDecorated = AsyncMock(name="mockedDecorated")
        return_value = "some return value"
        mockedDecorated.return_value = return_value
        # RateLimiter(**kwargs)

        # Act
        # pdb.set_trace()
        result = await self.rate_limited(mockedDecorated)(
            *coroutineArgs, **coroutineKwargs
        )
        
        # Assert
        self.mocked_async_limiter.assert_called_once_with(3, 1)
        self.assertEqual(result, return_value)
        mockedDecorated.assert_called_once_with(*coroutineArgs, **coroutineKwargs)

    async def test_wrapper_called_multiple(self):
        """Validate the wrapper is rate limiting the coroutine alongside all the args."""
        # Arrange
        coroutineArgs1 = "arg1"
        coroutineKwargs1 = {"kwarg1": "some value 1"}

        coroutineArgs2 = "arg2"
        coroutineKwargs2 = {"kwarg2": "some value 2"}

        mockedDecorated = AsyncMock(name="mockedDecorated")
        return_value1 = "some return value 1"
        return_value2 = "some return value 2"
        mockedDecorated.side_effect = [return_value1, return_value2]

        # Act
        result1 = await self.rate_limited(mockedDecorated)(coroutineArgs1, **coroutineKwargs1)
        result2 = await self.rate_limited(mockedDecorated)(coroutineArgs2, **coroutineKwargs2)

        # Assert
        self.mocked_async_limiter.assert_called_once_with(3, 1)
        self.assertEqual(result1, return_value1)
        self.assertEqual(result2, return_value2)
        mockedDecorated.assert_has_calls(
            [
                call(coroutineArgs1, **coroutineKwargs1),
                call(coroutineArgs2, **coroutineKwargs2),
            ]
        )


@pytest.mark.usefixtures("simulate_rate_limiting")
class TestRateLimitedFreq(unittest.IsolatedAsyncioTestCase):
    async def test_rate_limited_api(self):
        self.assertGreater(await self.rate_limited_caller(10), 4)