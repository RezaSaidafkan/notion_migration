from functools import wraps
from typing import Any, Callable, Concatenate, TypeVar, ParamSpec
from types import CoroutineType
import traceback

from migration_engine.repo.notion_object_mapping.notion_object_map import BasePage
from common_libs.singletons.tracing_singleton import Tracing
from common_libs.models.tracing import Body, Failure, Monad, TracePage, TracePageBody


P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")


def tracer[T, R, **P](
        coro: Callable[Concatenate[T, P], CoroutineType[Any, Any, R]]
    ) -> Callable[Concatenate[T, P], CoroutineType[Any, Any, R]]:
        """Docstring for tracer method decorator.
        
        :param coro: The async callable that is being decorated.
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
        
        @wraps(tracer)
        async def wrapper(instance: T, *args: P.args, **kwargs: P.kwargs) -> R:
            # 1. Extract 'page' from the arguments passed to the method.
            # We check kwargs first (common for named args), then look in args.
            page = kwargs.get("page")
            
            if page is None and args:
                # If page is the first positional arg after 'self', it's args[0]
                # Adjust index based on where 'page' usually sits in your methods.
                page = args[0] 

            try:
                # 2. Execute the original method as-is
                res = await coro(instance, *args, **kwargs)

                # 3. Use the extracted page for tracing
                if isinstance(page, BasePage):
                    tracing.send_trace_page(Body(
                        page=TracePage(id=page.Id.Id),
                        trace=TracePageBody(
                            function_name=f"{coro.__module__}.{coro.__name__}",
                            outcome=Monad(success=True, failure=None)
                        )
                    ))
                return res
            except Exception as e:
                # 4. Error tracing logic
                if isinstance(page, BasePage):
                    tracing.send_trace_page(
                        Body(
                            page=TracePage(id=page.Id.Id),
                            trace=TracePageBody(function_name=__name__ + ".query_database",
                                                outcome=Monad(success=False,
                                                            failure=Failure(
                                                                exception_type=str(type(e)),
                                                                exception_value=str(e),
                                                                exception_traceback=traceback.format_exc()
                                                                )
                                                            )
                                                )
                            )
                        )
                raise

        return wrapper

