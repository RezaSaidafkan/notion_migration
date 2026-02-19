from time import perf_counter
from typing import Any, Awaitable

from common_libs.models.client_models import CommonPage


async def timed(coro: Awaitable[Any], page: CommonPage, label: str, debug: bool = False) -> Any:
    if debug:
        t0 = perf_counter()
        res = await coro
        t1 = perf_counter()
        print(
            f"[TIMING] {label} \
              page={page.Id.Id, page.Properties.Title.title} \
              took={t1 - t0:.3f}s"
        )
    else:
        res = await coro
    return res
