from typing import Optional

from aiolimiter import AsyncLimiter
from typing_extensions import Self


class RateLimiterExeption(Exception):
    pass


class RateLimiter:
    _singleton = None

    def __new__(cls, max_rate: Optional[float]=None, time_period: Optional[int]=None) -> Self:
        if not cls._singleton:
            cls._singleton = super().__new__(cls)
        return cls._singleton

    def __init__(self, max_rate: Optional[float]=None, time_period: Optional[int]=None):
        if hasattr(self, "_initialized"):
            return
        if not max_rate and not time_period and not hasattr(self, "_initialized"):
            raise RateLimiterExeption("Rate Limiter was not properly initialzied.")
        if max_rate and time_period:
            self._rate_limiter = AsyncLimiter(max_rate, time_period)
            self._initialized = True
            self._max_rate = max_rate

    async def __aenter__(self):
        return self._rate_limiter

    async def __aexit__(self, exc_type, exc, tb):
        return None
