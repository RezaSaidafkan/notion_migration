from functools import wraps
from typing import Any, Callable, Dict

from aiolimiter import AsyncLimiter


# pylint: disable = invalid-name
class rate_limited:
    singleton_instance: Dict[Any, Any] = {}

    def __init__(self, max_rate: int, time_period: int):
        self._rate_limiter = AsyncLimiter(max_rate, time_period)

    def __new__(cls, *args, **kwargs):
        if not cls.singleton_instance:
            cls.singleton_instance[cls] = super(rate_limited, cls).__new__(cls)
        return cls.singleton_instance[cls]

    def __call__(self, coro: Callable[..., Any]) -> Any:
        @wraps(self.__call__)
        async def wrapper(*args, **kwargs) -> Any:
            async with self._rate_limiter:
                return await coro(*args, **kwargs)

        return wrapper
