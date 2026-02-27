from functools import wraps
from unittest.mock import patch

import config
import pytest
from common_libs.utils.tracing import tracer
from common_libs.utils.rate_limiter import rate_limited


def bridger(original_decorator):
    @wraps(bridger)
    def bridge_decorator(decorated_func):
        @wraps(bridge_decorator)
        async def bridge_wrapper(*args2, **kwargs2):
            if config.decorator_mock_activated:
                #decorated_func = actual_decorator.__wrapped__
                '''
                Only calls the enclosed function, no extra side effects
                '''
                return await decorated_func(*args2, **kwargs2)
            else:
                return await original_decorator(decorated_func)(*args2, **kwargs2)
        return bridge_wrapper
    return bridge_decorator


tracing_patch = patch('common_libs.utils.tracing.tracer', bridger(tracer))
rate_limited_patch = patch('common_libs.utils.rate_limiter.rate_limited', bridger(rate_limited))

tracing_patch.start()
rate_limited_patch.start()

@pytest.fixture(scope="session", autouse=True)
def apply_mocked_decorators():
    yield
    tracing_patch.stop()
    rate_limited_patch.stop()
