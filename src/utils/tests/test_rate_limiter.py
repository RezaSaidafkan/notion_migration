import unittest
from unittest.mock import AsyncMock, call, patch

from src.utils.rate_limiter import rate_limited


class TestRateLimited(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.patched_async_limiter = patch("src.utils.rate_limiter.AsyncLimiter")
        self.mocked_async_limiter = self.patched_async_limiter.start()

    def test_singleton(self):
        """Validate only a single instance created throught multiple calls"""
        # Arrange
        kwargs1 = {"time_period": 1, "max_rate": 3}
        kwargs2 = {"time_period": 2, "max_rate": 3}
        # Act
        singleton_1 = rate_limited(**kwargs1)
        singleton_2 = rate_limited(**kwargs2)

        # Assert
        assert singleton_1 == singleton_2

    def test_not_passing_arg(self):
        """Validate the class decorator raises when required args & kwargs are not passed"""
        # Arrange & Act & Assert
        with self.assertRaises(TypeError):
            rate_limited()

    def test_passing_correct_args(self):
        """Validate the class decorator passes when required args & kwargs are passed"""
        # Arrange
        kwargs = {"time_period": 1, "max_rate": 3}

        # Act & Assert
        self.assertIsNotNone(rate_limited(**kwargs))

    async def test_wrapper_called_once(self):
        """Validate the wrapper is rate limiting the coroutine alongside all the args"""
        # Arrange
        kwargs = {"time_period": 1, "max_rate": 3}
        coroutineArgs = "arg1"
        coroutineKwargs = {"kwarg": "some value"}
        mockedCoroutine = AsyncMock()
        return_value = "some return value"
        mockedCoroutine.return_value = return_value

        # Act
        result = await rate_limited(**kwargs)(mockedCoroutine)(
            *coroutineArgs, **coroutineKwargs
        )

        # Assert
        self.mocked_async_limiter.assert_called_once_with(3, 1)
        self.assertEqual(result, return_value)
        mockedCoroutine.assert_called_once_with(*coroutineArgs, **coroutineKwargs)

    async def test_wrapper_called_multiple(self):
        """Validate the wrapper is rate limiting the coroutine alongside all the args"""
        # Arrange
        kwargs = {"time_period": 1, "max_rate": 3}
        coroutineArgs1 = "arg1"
        coroutineKwargs1 = {"kwarg1": "some value 1"}

        coroutineArgs2 = "arg2"
        coroutineKwargs2 = {"kwarg2": "some value 2"}

        mockedCoroutine = AsyncMock()
        return_value1 = "some return value 1"
        return_value2 = "some return value 2"
        mockedCoroutine.side_effect = [return_value1, return_value2]

        # Act
        result1 = await rate_limited(**kwargs)(mockedCoroutine)(
            *coroutineArgs1, **coroutineKwargs1
        )
        result2 = await rate_limited(**kwargs)(mockedCoroutine)(
            *coroutineArgs2, **coroutineKwargs2
        )

        # Assert
        self.mocked_async_limiter.assert_called_with(3, 1)
        assert self.mocked_async_limiter.call_count == 2
        self.assertEqual(result1, return_value1)
        self.assertEqual(result2, return_value2)
        mockedCoroutine.assert_has_calls(
            [
                call(*coroutineArgs1, **coroutineKwargs1),
                call(*coroutineArgs2, **coroutineKwargs2),
            ]
        )

    def tearDown(self):
        self.mocked_async_limiter.stop()
