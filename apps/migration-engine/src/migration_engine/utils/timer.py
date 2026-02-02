from time import perf_counter
from typing import Any

from common_libs.models.client_models import P
from migration_engine.config.load_config import GLOBAL_CONFIG


async def _timed(coro, page: P, label: str, debug: bool | None = None) -> Any:
    if debug is None:
        debug = GLOBAL_CONFIG.debug
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
