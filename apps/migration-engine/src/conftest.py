from functools import wraps
from typing import Any, Callable
from unittest.mock import patch

import config
import pytest
from common_libs.utils.rate_limiter import rate_limited
from common_libs.utils.tracing import tracer


def bridger(original_decorator: Callable[..., Callable[..., Any]]):
    @wraps(original_decorator)
    def bridge_decorator(decorated_func: Callable[..., Any]):
        @wraps(decorated_func)
        async def bridge_wrapper(*args2: Any, **kwargs2: Any):
            if config.DECORATOR_MOCK_ACTIVATED:
                # Only calls the enclosed function, no extra side effects
                return await decorated_func(*args2, **kwargs2)
            return await original_decorator(decorated_func)(*args2, **kwargs2)
        return bridge_wrapper
    return bridge_decorator


TRACING_PATCH = patch('common_libs.utils.tracing.tracer', bridger(tracer))
RATE_LIMITED_PATCH = patch('common_libs.utils.rate_limiter.rate_limited', bridger(rate_limited))

TRACING_PATCH.start()
RATE_LIMITED_PATCH.start()

@pytest.fixture(scope="session", autouse=True)
def apply_mocked_decorators():
    yield
    TRACING_PATCH.stop()
    RATE_LIMITED_PATCH.stop()
