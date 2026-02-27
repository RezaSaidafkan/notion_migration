from functools import wraps
from typing import Any, Callable, Coroutine, Awaitable
from common_libs.singletons.rate_limiter_singleton import RateLimiter
    


# pylint: disable = invalid-name
def rate_limited(coro: Callable[..., Coroutine[Any, Any, Any]]) -> Awaitable[Any]:
    @wraps(rate_limited)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        async with RateLimiter() as rl:
            print('CCCCAAAAALLLLIIIING RATE LIMITER')
            async with rl:
                print("CAAAAPPAAAACCCITYYYY 1", rl.has_capacity(0), rl.has_capacity(1), rl.has_capacity(2), rl.has_capacity(3), rl)
                print("CCCCCOOOURRR", coro, args, kwargs)
                result = await coro(*args, **kwargs)
                print("REEESSSSSUUUUUULLLLT")
                print("CAAAAPPAAAACCCITYYYY 2", rl.has_capacity(0), rl.has_capacity(1), rl.has_capacity(2), rl.has_capacity(3), rl)
                return result
    return wrapper

    