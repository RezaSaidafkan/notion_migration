from collections.abc import Coroutine
from functools import wraps
from typing import Any, Callable, Concatenate

from common_libs.singletons.rate_limiter_singleton import RateLimiter


# pylint: disable = invalid-name
def rate_limited[T, R, **P](
        coro: Callable[Concatenate[T, P], Coroutine[Any, Any, R]]
    ) -> Callable[Concatenate[T, P], Coroutine[Any, Any, R]]:
    @wraps(coro)
    async def wrapper(*args: Any, **kwargs: Any) -> R:
        async with RateLimiter() as rl:
            try:
                async with rl:
                    result = await coro(*args, **kwargs)
                    return result
            except (BaseException, Exception) as e:
                raise e
    return wrapper
