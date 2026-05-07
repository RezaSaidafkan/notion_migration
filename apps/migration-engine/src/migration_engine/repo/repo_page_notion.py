import logging
from abc import abstractmethod
from asyncio import Event
from dataclasses import dataclass
from functools import wraps
from logging import Logger
from typing import Any, Callable, Concatenate, Coroutine, Generic, List, Optional, cast
from uuid import UUID

from common_libs.constants.literal_definitions import RelationDefinitions
from common_libs.models.api_models import ApiPage
from common_libs.models.client_models import (
    BasePage,
    C,
    JournalPage,
    JournalProperties,
    PageId,
    PageUpdate,
    PaginationResult,
    TaskPage,
    TaskProperties,
)
from common_libs.models.context import ExecutionContext
from common_libs.utils.rate_limiter import rate_limited
from common_libs.utils.tracing import tracer
from httpcore import ConnectError
from notion_client import AsyncClient as Client
from notion_client.errors import (
    APIErrorCode,
    APIResponseError,
    HTTPResponseError,
    RequestTimeoutError,
)
from pydantic import ValidationError
from tenacity import (
    RetryCallState,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    retry_if_not_exception_type,
    wait_exponential,
)
from tenacity.stop import stop_base
from tenacity.wait import wait_base

from migration_engine.repo.notion_object_mapping.notion_object_map import translate
from migration_engine.repo.repo_page_interface import (
    QueryType,
    RepositoryError,
    RepositoryInterface,
)

logger = logging.getLogger(__name__)
logger_client: Logger = logger.getChild("client")

ATTEMPT_TRIAL_NUMBER = 5
RETRY_TIMEOUT_FALLBACK = 1  # in seconds

EVENT = Event()
EVENT.set()
ACTIVE_CALL_ID: Optional[UUID] = None  # Tracking which call is allowed through the gate

def error_handling[T, R, **P](
    coro: Callable[Concatenate[T, P], Coroutine[Any, Any, R]]
) -> Callable[Concatenate[T, P], Coroutine[Any, Any, R]]:
    @wraps(coro)
    async def wrapper(instance: T, *args: P.args, **kwargs: P.kwargs) -> R:
        try:
            result = await coro(instance, *args, **kwargs)
            return result
        except KeyError as ke:
            raise RepositoryError(
                message = "Failed to parse API response to internal model",
                error_type = type(ke)
                ) from None
        except ConnectError as c_e:
            raise RepositoryError(
                error_type=type(c_e)
                ) from None
        except RequestTimeoutError as rto_e:
            logger.exception(rto_e)
            raise RepositoryError(
                code = rto_e.code,
                error_type = type(rto_e)
                ) from None
        except APIResponseError as api_e:
            logger.exception(api_e)
            raise RepositoryError(
                code= api_e.code,
                status= api_e.status,
                error_type= type(api_e)
                ) from None
        except HTTPResponseError as hr_e:
            raise RepositoryError(
                code=hr_e.code,
                status=hr_e.status,
                error_type=type(hr_e)
                ) from None
        except ValidationError as validation_e:
            raise RepositoryError(
                message=validation_e.json(),
                error_type=type(validation_e)
                ) from None
        except Exception as e:
            raise RepositoryError(
                error_type=type(e),
                message=str(e)
                ) from None
    return wrapper

# pylint: disable=invalid-name, too-few-public-methods
class wait_error_callback(wait_base):
    def __init__(self) -> None:
        pass

    def __call__(self, retry_state: RetryCallState) -> float:
        page = cast(BasePage, retry_state.kwargs.get("page"))

        # setting the Active Call ID to be used by `synchronization_gating`
        global ACTIVE_CALL_ID  # noqa: PLW0603, pylint: disable=global-statement
        ACTIVE_CALL_ID = page.Id.Id

        EVENT.clear()
        logger.debug("%s: '%s', '%s'", repr(retry_state), page.Id.Id, EVENT)
        if retry_state.outcome:
            exception = retry_state.outcome.exception()
            if isinstance(exception, APIResponseError) and \
                exception.code == APIErrorCode.RateLimited:
                if "Retry-After" in exception.headers:
                    retry_timeout = exception.headers.get("Retry-After")
                    return float(retry_timeout)
                wait_exponential_instance = wait_exponential(multiplier=1, min=10, max=90)
                retry_timeout = wait_exponential_instance(retry_state)
                return retry_timeout
        return RETRY_TIMEOUT_FALLBACK


class stop_after_attempt_dynamic(stop_base):
    def __init__(self) -> None:
        pass

    def __call__(self, retry_state: RetryCallState) -> bool:
        return retry_state.attempt_number >= ATTEMPT_TRIAL_NUMBER

# pylint: disable=unused-argument
def set_on_exhausted(retry_state: RetryCallState):
    EVENT.set()
    global ACTIVE_CALL_ID  # noqa: PLW0603, pylint: disable=global-statement
    ACTIVE_CALL_ID = None
    logger.debug("Retry loop exhausted, EVENT is 'Set'")

def synchronization_gating[T, R, **P](
    coro: Callable[Concatenate[T, P], Coroutine[Any, Any, R]]
) -> Callable[Concatenate[T, P], Coroutine[Any, Any, R]]:
    @wraps(coro)
    async def wrapper(instance: T, *args: P.args, **kwargs: P.kwargs) -> R:
        page = cast(BasePage, kwargs.get("page"))
        execution_context = cast(ExecutionContext, kwargs.get("execution_context"))

        call_id = page.Id.Id

        global ACTIVE_CALL_ID  # noqa: PLW0603, pylint: disable=global-statement
        if execution_context.debug:
            logger.debug("ACTIVE_CALL_ID: '%s', EVENT: '%s'", ACTIVE_CALL_ID, EVENT)
        while not EVENT.is_set() and ACTIVE_CALL_ID != call_id:
            if execution_context.debug:
                logger.debug("Stalled processing PageId '%s': \
Another call is active, wait for it to finish", call_id)
            await EVENT.wait()
            continue

        if EVENT.is_set() and execution_context.debug:
            logger.debug(
                "Executing the API call: '%s', Event is 'Set': '%s'", page.Id.Id, EVENT.is_set())
        elif not EVENT.is_set() and ACTIVE_CALL_ID != page.Id.Id:
            if execution_context.debug:
                logger.debug(
                    "Waiting to executing the API call: '%s', Event is 'Set': '%s'",
                    page.Id.Id, EVENT.is_set())
            await EVENT.wait()

        response: Any = None
        response = await coro(instance, *args, **kwargs)

        if ACTIVE_CALL_ID == page.Id.Id:
            EVENT.set()
            ACTIVE_CALL_ID = None
            if execution_context.debug:
                logger.debug("Queried successfully, EVENT is 'Set': '%s'", page.Id.Id)
        logger.debug("Successfully executed the API call: '%s'", page.Id.Id)
        return response
    return wrapper

# pylint: disable=too-few-public-methods
class ClientSingleton:
    _instance = None

    def __new__(cls, *args: Any, **kwargs: Any):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, notion_token: str, time_out_ms: float, debug: bool):
        self.notion = Client(auth=notion_token,
                             timeout_ms=time_out_ms,
                             logger=logger_client,
                             log_level=logging.WARNING if debug else logging.INFO)


class NotionRepository(
    Generic[C], RepositoryInterface[BasePage, C, RelationDefinitions], ClientSingleton):
    # pylint: disable=invalid-overridden-method
    async def read_page(self, page: BasePage, debug: bool=False) -> C:
        try:
            raw_result = await self.notion.pages.retrieve(page_id=str(page.Id.Id))
            api_page = ApiPage(**raw_result)
            page = self.convert_client_page(api_page)
            return page
        except APIResponseError as api_e:
            raise RepositoryError(
                error_type=type(api_e),
                message=f"Failed to retrieve page {page}"
                ) from api_e
        except ValidationError as ve:
            raise RepositoryError(
                error_type=type(ve),
                message=f"Failed to validate response with the model for page {page}"
                ) from ve
        except Exception as e:
            raise RepositoryError(
                error_type=type(e)) from None

    @abstractmethod
    def convert_client_page(self, result: ApiPage) -> C:
        pass

    # pylint: disable=too-many-positional-arguments, too-many-arguments, too-many-locals
    # pylint: disable=unused-argument, global-statement
    @error_handling
    @rate_limited
    @retry(
        reraise=True,
        retry=retry_if_not_exception_type(
            (RequestTimeoutError, HTTPResponseError, APIResponseError)),
        retry_error_callback=set_on_exhausted,
        )
    @retry(
        reraise=True,
        retry=retry_if_exception_type(
            (RequestTimeoutError, HTTPResponseError, APIResponseError)),
        wait=wait_error_callback(),
        before_sleep=before_sleep_log(logger, logging.DEBUG),
        retry_error_callback=set_on_exhausted,
        stop=stop_after_attempt_dynamic(),
        )
    @tracer
    @synchronization_gating
    async def _read_query_database(
        self,
        page: BasePage,
        execution_context: ExecutionContext,
        data_source_id: UUID,
        relation: RelationDefinitions,
        cursor: str | None = None,
    ) -> PaginationResult[C]:

        query: QueryType = {}
        response: Any = None

        filter_query = translate(relation=relation, page=page)

        query["filter"] = filter_query if filter_query else {}
        query["page_size"] = execution_context.page_size
        if cursor:
            query["start_cursor"] = cursor

        response = await self.notion.data_sources.query(str(data_source_id), **query)

        results = [ApiPage(**result) for result in response["results"]]
        converted_results: List[C] = [
            self.convert_client_page(apiPage) for apiPage in results
        ]

        result = PaginationResult[C](
            results=converted_results,
            has_more=response["has_more"],
            next_cursor=response.get("next_cursor"),
        )
        logger.debug("Result for '%s': '%s' hits.", page.Id.Id, len(result.results))
        return result

    @tracer
    async def query_database(
        self,
        page: BasePage,
        execution_context: ExecutionContext,
        data_source_id: UUID,
        relation: RelationDefinitions,
        cursor: str | None = None,
    ) -> PaginationResult[C]:
        return await self._read_query_database(
            page=page,
            execution_context=execution_context,
            data_source_id=data_source_id,
            relation=relation,
            cursor=cursor)

    @tracer
    async def create_page(
        self,
        page: C,
        execution_context: ExecutionContext,
        parent_page_id: UUID,
        debug: bool) -> bool:
        return await self._create_page(
            page=page,
            execution_context=execution_context,
            parent_page_id=parent_page_id,
            debug=debug)

    # pylint: disable=too-many-positional-arguments, too-many-arguments, too-many-locals
    # pylint: disable=unused-argument, global-statement
    @error_handling
    @rate_limited
    @retry(
        reraise=True,
        retry=retry_if_not_exception_type(
            (RequestTimeoutError, HTTPResponseError, APIResponseError)),
        retry_error_callback=set_on_exhausted,
        )
    @retry(
        reraise=True,
        retry=retry_if_exception_type(
            (RequestTimeoutError, HTTPResponseError, APIResponseError)),
        wait=wait_error_callback(),
        before_sleep=before_sleep_log(logger, logging.DEBUG),
        retry_error_callback=set_on_exhausted,
        stop=stop_after_attempt_dynamic(),
        )
    @tracer
    @synchronization_gating
    async def _create_page(
        self,
        page: C,
        execution_context: ExecutionContext,
        parent_page_id: UUID,
        debug: bool
        ) -> bool:
        result = await self.notion.pages.create(
            **{
                "parent": {
                    "data_source_id": str(parent_page_id)
                },
                },
            **page.model_dump(mode="json", by_alias=True, exclude={"Id"})
            )
        if debug:
            logger.debug("Page created: %s", result)
        return True

    # pylint: disable=too-many-positional-arguments, too-many-arguments, too-many-locals
    # pylint: disable=unused-argument, global-statement
    @error_handling
    @rate_limited
    @retry(
        reraise=True,
        retry=retry_if_not_exception_type(
            (RequestTimeoutError, HTTPResponseError, APIResponseError)),
        retry_error_callback=set_on_exhausted,
        )
    @retry(
        reraise=True,
        retry=retry_if_exception_type(
            (RequestTimeoutError, HTTPResponseError, APIResponseError)),
        wait=wait_error_callback(),
        before_sleep=before_sleep_log(logger, logging.DEBUG),
        retry_error_callback=set_on_exhausted,
        stop=stop_after_attempt_dynamic(),
        )
    @tracer
    @synchronization_gating
    async def update_page(
        self,
        page: C,
        execution_context: ExecutionContext,
        parent_page: UUID,
        update_properties: PageUpdate,
        debug: bool
    ) -> bool:
        # constrain the PageUpdate.Properties to parent_page:
        # Datasource (the type is not implemented yet)
        # To change the properties of a page in a data source, use the properties body parameter.
        # This parameter can only be used if the page’s parent is a data source,
        # aside from updating the title of a page outside of a data source.
        return await self._update_page(
            page=page,
            execution_context=execution_context,
            parent_page=parent_page,
            update_properties=update_properties,
            debug=debug)

    @tracer
    async def _update_page(
        self,
        page: C,
        execution_context: ExecutionContext,
        parent_page: UUID,
        update_properties: PageUpdate,
        debug: bool
    ) -> bool:
        result = await self.notion.pages.update(
            page_id=str(page.Id.Id),
            **update_properties.model_dump(mode="json", by_alias=True, exclude={"Id"})
            )
        if debug:
            logger.debug("Page updated: '%s'", result)
        return True


class NotionRepoSource(NotionRepository[TaskPage]):
    def convert_client_page(self, result: ApiPage) -> TaskPage:
        try:
            props = result.properties
            # Build client-facing properties using the typed dataclasses
            client_props = TaskProperties(
                Type=props.Type,
                Title=props.Title,
                Assignee=props.Assignee,
                Priority=props.Priority,
                Urgency=props.Urgency,
                Status=props.Status,
                Timeline=props.Timeline,
                Description=props.Description,
            )
            return TaskPage(
                Id=PageId(Id=result.id), Icon=result.icon, Properties=client_props
            )
        except ValidationError as e:
            raise RepositoryError(
                message=f"Failed to parse API response to Page: '{e}'\n{result}"
            ) from e


class NotionRepoJournal(NotionRepository[JournalPage]):
    def convert_client_page(self, result: ApiPage) -> JournalPage:
        try:
            props = result.properties

            # Build client-facing properties using the typed dataclasses
            client_props = JournalProperties(
                Type=props.Type,
                Title=props.Title,
                Status=props.Status,
                Timeline=props.Timeline,
                Description=props.Description,
            )
            return JournalPage(
                Id=PageId(Id=result.id), Icon=result.icon, Properties=client_props
            )
        except ValidationError as e:
            raise RepositoryError(
                message=f"Failed to parse API response to JournalPage:'{e}'\n{result}"
            ) from e


@dataclass
class RepositoryDirectInjection:
    source_repo: NotionRepoSource
    journal_repo: NotionRepoJournal
