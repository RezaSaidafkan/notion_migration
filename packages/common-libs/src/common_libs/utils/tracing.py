from functools import wraps
from typing import Any, Callable, Concatenate, Coroutine

import httpx
from migration_engine.repo.notion_object_mapping.notion_object_map import PageId

from common_libs.models.tracing import Body, Failure, Monad, TracePage, TracePageBody


class TracingException(Exception):
    pass


class Tracing:
    def __init__(self, address: str, port: int) -> None:
        self._address = address
        self._port = port
        self._url = f"http://{self._address}:{self._port}"


    def send_trace_page(self, body: Body):
        try:
            with httpx.Client() as client:
                response = client.post(f"{self._url}/trace_page", json=body.model_dump(mode="json"))
                response.raise_for_status()
        except httpx.HTTPError as t_e:
            raise TracingException(
                f"Failed to send tracing for:\t{body.page.id}\t{body.trace.function_name}") from t_e
        except Exception as e:
            raise TracingException(
                f"Unknown issue is sending tracing for:\
                    \t{body.page.id}\t{body.trace.function_name}") from e

    def __call__[R, **P](
        self,
        coro: Callable[Concatenate[Any, PageId, P],  Coroutine[Any, Any, R]])\
            -> Callable[Concatenate[Any, PageId, P], Coroutine[Any, Any, R]]:
        """Docstring for tracer method decorator.
        
        :param coro: The async callable that is being decorated.
            The parameters are type safely divided into:
            'Any' -> to pass the object the method belongs to, standing in for 'self'.
            'PageId' -> the second positional argument.
            'P': ParamSec -> to get the rest of parameter signatures of the callable.
                These TypeVars are organized by Concatenated 
            'R': TypeVar -> to represent the return value of the callable.
        :type coro: Callable[Concatenate[Any, PageId, ExecutionContext, P], Coroutine[Any, Any, R]]
        :return: The wrapper async function; a callable.
        :rtype: Callable[Concatenate[Any, PageId, ExecutionContext, P], Coroutine[Any, Any, R]]
        """
        send_trace_page = self.send_trace_page

        @wraps(coro)
        async def wrapper(
            self: Any,
            page_id: PageId,
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> R:
            try:
                res = await coro(self, page_id, *args, **kwargs)

                send_trace_page(Body(
                                page=TracePage(id=page_id.Id),
                                trace=TracePageBody(function_name=__name__ + ".query_database",
                                            outcome=Monad(success=True,
                                                            failure=None)
                                                )
                                )
                    )
                return res
            except Exception as e:
                send_trace_page(
                                Body(
                                    page=TracePage(id=page_id.Id),
                                    trace=TracePageBody(function_name=__name__ + ".query_database",
                                                outcome=Monad(success=False,
                                                                failure=Failure(
                                                                    exception_type=str(type(e)),
                                                                    exception_value=str(e),
                                                                exception_traceback=""
                                                                )
                                                            )
                                                        )
                                        )
                )
                raise

        return wrapper
