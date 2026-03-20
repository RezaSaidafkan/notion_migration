import logging
import traceback
from collections.abc import Coroutine
from functools import wraps
from typing import Any, Callable, Concatenate, cast
from venv import logger

from migration_engine.repo.notion_object_mapping.notion_object_map import BasePage

from common_libs.models.context import ExecutionContext
from common_libs.models.tracing_models import (
    Body,
    Failure,
    Monad,
    TracePage,
    TracePageBody,
)
from common_libs.singletons.tracing_singleton import Tracing, TracingException


def tracer[T, R, **P](
        coro: Callable[Concatenate[T, P], Coroutine[Any, Any, R]]
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
    tracing = Tracing()

    @wraps(coro)
    async def wrapper(instance: T, *args: P.args, **kwargs: P.kwargs) -> R:
        # 1. Extract 'page' from the arguments passed to the method.
        # We check kwargs first (common for named args), then look in args.
        page = cast(BasePage, kwargs.get("page"))
        execution_context = cast(ExecutionContext, kwargs.get("execution_context"))

        try:
            # 2. Execute the original method as-is
            res = await coro(instance, *args, **kwargs)

            # 3. Use the extracted page for tracing
            tracing.send_trace_page(
                Body(
                    execution_id=execution_context.execution_id,
                    page=TracePage(id=page.Id.Id),
                    trace=TracePageBody(
                        function_name=f"{coro.__module__}.{coro.__name__}",
                        outcome=Monad(success=True, failure=None)
                    )
                )
            )
            return res
        except TracingException as te:
            logger.debug("Caught! AAA")
            logging.exception(
                "Tracing failed: %s", te)
            raise
        except Exception as e:
            logger.debug("Caught! AAA")
            # 4. Error tracing logic
            tracing.send_trace_page(
                Body(
                    execution_id=execution_context.execution_id,
                    page=TracePage(id=page.Id.Id),
                    trace=TracePageBody(function_name=__name__ + ".query_database",
                                        outcome=Monad(
                                            success=False,
                                            failure=Failure(
                                                    exception_type=str(type(e)),
                                                    exception_value=str(e),
                                                    exception_traceback=traceback.format_exc()
                                                    )
                                                )
                                        )
                    )
                )
            logger.debug("SENT! AAA")
            raise
    return wrapper
