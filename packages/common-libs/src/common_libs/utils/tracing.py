import logging
import traceback
from collections.abc import Coroutine
from functools import wraps
from typing import Any, Callable, Concatenate, cast

from migration_engine.repo.notion_object_mapping.notion_object_map import BasePage
from tracing.db.models.table import Stage

from common_libs.models.context import ExecutionContext
from common_libs.models.monad_models import Failure, Monad
from common_libs.models.tracing_models import (
    TracePage,
    TracePageBody,
)
from common_libs.singletons.tracing_singleton import Tracing, TracingException

logger = logging.getLogger(__name__)


def tracer(stage: Stage):
    def tracer_wrapper[T, R, **P](
        coro: Callable[Concatenate[T, P], Coroutine[Any, Any, R]],
        stage_arg: Stage = stage
    ) -> Callable[Concatenate[T, P], Coroutine[Any, Any, R]]:
        """:param coro: The async callable that is being decorated.
            The parameters are type safely divided into:
            'Any' -> to pass the object the method belongs to, standing in for 'self'.
            'BasePage' -> the second positional argument.
            'P': ParamSec -> to get the rest of parameter signatures of the callable.
                These TypeVars are organized by Concatenated
            'R': TypeVar -> to represent the return value of the callable.
        :type coro: Callable[Concatenate[Any, BasePage, P], Coroutine[Any, Any, R]]
        :return: The wrapper async function; a callable.
        :rtype: Callable[Concatenate[Any, BasePage, P], Coroutine[Any, Any, R]]
        """
        @wraps(coro)
        async def wrapper(instance: T, *args: P.args, **kwargs: P.kwargs) -> R:
            # Get the singleton lazily so it's initialized with proper config
            tracing = Tracing()
            # 1. Extract 'page' and 'execution_context' from args or kwargs
            page = cast(BasePage, kwargs.get("page"))
            execution_context = cast(ExecutionContext, kwargs.get("execution_context"))

            try:
                # 2. Execute the original method as-is
                res = await coro(instance, *args, **kwargs)

                # 3. Use the extracted page for tracing (only if we have valid context)
                tracing.send_trace_page(
                    TracePage(
                        execution_id=execution_context.execution_id,
                        page_id=page.Id,
                        trace=TracePageBody(
                            function_name=f"{coro.__module__}.{coro.__name__}",
                            outcome=Monad(success=True, failure=None)
                        ),
                        stage=stage_arg
                    )
                )
                return res
            except TracingException as te:
                logger.exception("Tracing failed: %s", te)
                raise
            except (BaseException, Exception) as e:
                # 4. Error tracing logic (only if we have valid context)
                try:
                    tracing.send_trace_page(
                        TracePage(
                            execution_id=execution_context.execution_id,
                            page_id=page.Id,
                            trace=TracePageBody(
                                function_name=f"{coro.__module__}.{coro.__name__}",
                                outcome=Monad(
                                    success=False,
                                    failure=Failure(
                                        exception_type=str(type(e).__name__),
                                        exception_value=str(e),
                                        exception_traceback=traceback.format_exc()
                                    )
                                )
                            ),
                            stage=stage_arg
                        )
                    )

                except TracingException as te:
                    logger.exception("Failed to send error trace: %s", type(te).__name__)
                raise
        return wrapper
    return tracer_wrapper
