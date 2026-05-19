import logging
from time import perf_counter
from typing import Any, Awaitable

from common_libs.models.client_models import JournalPage, TaskPage

logger = logging.getLogger()


async def timed(
    coro: Awaitable[Any],
    page: TaskPage | JournalPage,
    label: str,
    debug: bool = False) -> Any:
    if debug:
        t0 = perf_counter()
        res = await coro
        t1 = perf_counter()
        logger.debug(
            "[TIMING] %s \
              page=%s %s \
              took=%.3fs",
              label,
              page.Id.Id, page.Properties.Title.title,
              t1 - t0
        )
    else:
        res = await coro
    return res
