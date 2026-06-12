import logging
from abc import abstractmethod
from asyncio import Event
from dataclasses import dataclass
from functools import wraps
from logging import Logger
from typing import (
    Any,
    Callable,
    Concatenate,
    Coroutine,
    Dict,
    Generic,
    List,
    Optional,
    cast,
)
from uuid import UUID

from common_libs.constants.literal_definitions import RelationDefinitions
from common_libs.models.api_models import ApiJournalPage, ApiTaskPage
from common_libs.models.client_models import (
    BasePage,
    C,
    JournalPage,
    JournalProperties,
    PageId,
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
from tracing.db.models.table import (
    SourcePageExtraction,
    SourcePageRelatedExtraction,
    TargetPageLoaded,
    TargetPageRelationsLoaded,
)

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
    # Re-raise the last exception encountered during retries so it can be traced
    if retry_state.outcome:
        retry_state.outcome.result()  # This will raise the original exception


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
    @abstractmethod
    def convert_client_page(self, result: Dict[str, Any]) -> C:
        pass

    @abstractmethod
    async def read_page(self, page: BasePage, execution_context: ExecutionContext) -> C:
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
        stop=stop_after_attempt_dynamic(),
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
    @tracer(SourcePageExtraction())
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

        converted_results: List[C] = [
            self.convert_client_page(result) for result in response["results"]
        ]

        result = PaginationResult[C](
            results=converted_results,
            has_more=response["has_more"],
            next_cursor=response.get("next_cursor"),
        )
        logger.debug("Result for '%s': '%s' hits.", page.Id.Id, len(result.results))
        return result

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

    @tracer(TargetPageRelationsLoaded())
    async def update_target_page(
        self,
        page: C,
        execution_context: ExecutionContext,
        parent_page_id: Optional[UUID] = None,
    ) -> bool:
        # constrain the PageUpdate.Properties to parent_page:
        # Datasource (the type is not implemented yet)
        # To change the properties of a page in a data source, use the properties body parameter.
        # This parameter can only be used if the page’s parent is a data source,
        # aside from updating the title of a page outside of a data source.
        return await self._update_page(
            page=page,
            execution_context=execution_context,
            parent_page_id=parent_page_id,
            )

    @tracer(SourcePageRelatedExtraction())
    async def update_source_page(
        self,
        page: C,
        execution_context: ExecutionContext,
        parent_page_id: Optional[UUID] = None,
    ) -> bool:
        # constrain the PageUpdate.Properties to parent_page:
        # Datasource (the type is not implemented yet)
        # To change the properties of a page in a data source, use the properties body parameter.
        # This parameter can only be used if the page’s parent is a data source,
        # aside from updating the title of a page outside of a data source.
        return await self._update_page(
            page=page,
            execution_context=execution_context,
            parent_page_id=parent_page_id,
            )

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
    @synchronization_gating
    @tracer(SourcePageRelatedExtraction())
    async def _update_page(
        self,
        page: C,
        execution_context: ExecutionContext,
        parent_page_id: Optional[UUID] = None,
    ) -> bool:
        payload = page.model_dump(
            mode="json",
            by_alias=True,
            exclude={
                "Id": True,
                "properties": {"Assignee": True}
                },
            exclude_unset=True)
        del payload["properties"]["Assignee"]
        result = await self.notion.pages.update(
            page_id=str(page.Id.Id),
            **payload
            )
        if execution_context.debug:
            logger.debug("Page updated: '%s'", result)
        return True

    async def create_page(
        self,
        page: C,
        execution_context: ExecutionContext,
        parent_page_id: UUID
    ) -> C:
        result = await self._create_page(
            page=page,
            execution_context=execution_context,
            parent_page_id=parent_page_id)
        return result

    # pylint: disable=too-many-positional-arguments, too-many-arguments, too-many-locals
    # pylint: disable=unused-argument, global-statement
    @retry(
        reraise=True,
        retry=retry_if_not_exception_type(
            (RequestTimeoutError, HTTPResponseError, APIResponseError, RuntimeError)),
        retry_error_callback=set_on_exhausted,
        stop=stop_after_attempt_dynamic(),
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
    @tracer(TargetPageLoaded())
    @synchronization_gating
    async def _create_page(
        self,
        page: C,
        execution_context: ExecutionContext,
        parent_page_id: UUID
    ) -> C:
        payload = page.model_dump(
            mode="json",
            by_alias=True,
            exclude={
                "Id": True,
                "properties": {"Assignee": True}
                },
            exclude_unset=True)
        if "Assignee" in payload["properties"]:
            del payload["properties"]["Assignee"]

        result = await self.notion.pages.create(
            **{
                "parent": {
                    "data_source_id": str(parent_page_id)
                    },
                },
            **payload
            )
        page_created = self.convert_client_page(result)
        if execution_context.debug:
            logger.debug("Page created: %s", page_created)
        return page_created


class NotionRepoSource(NotionRepository[TaskPage]):
    # pylint: disable=invalid-overridden-method
    async def read_page(self, page: BasePage, execution_context: ExecutionContext) -> TaskPage:
        try:
            raw_result = await self.notion.pages.retrieve(page_id=str(page.Id.Id))
            task_page = self.convert_client_page(raw_result)
            if execution_context.debug:
                logger.debug("JouranlPage retrieved: %s", task_page)
            return task_page
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
                error_type=type(e),
                message=str(e),
                ) from None


    def convert_client_page(self, result: Dict[str, Any]) -> TaskPage:
        try:
            api_task_page = ApiTaskPage(**result)
            # Build client-facing properties using the typed dataclasses
            client_props = TaskProperties(
                Type=api_task_page.properties.Type,
                Title=api_task_page.properties.Title,
                Assignee=api_task_page.properties.Assignee,
                Priority=api_task_page.properties.Priority,
                Urgency=api_task_page.properties.Urgency,
                Status=api_task_page.properties.Status,
                Timeline=api_task_page.properties.Timeline,
                Description=api_task_page.properties.Description,
            )
            return TaskPage(
                Id=PageId(Id=api_task_page.id), Icon=api_task_page.icon, Properties=client_props
            )
        except ValidationError as e:
            raise RepositoryError(
                message=f"Failed to parse API response to Page: '{e}'\n{result}"
            ) from e


class NotionRepoJournal(NotionRepository[JournalPage]):
    # pylint: disable=invalid-overridden-method
    async def read_page(self, page: BasePage, execution_context: ExecutionContext) -> JournalPage:
        try:
            raw_result = await self.notion.pages.retrieve(page_id=str(page.Id.Id))
            journal_page = self.convert_client_page(raw_result)
            if execution_context.debug:
                logger.debug("TaskPage retrieved: %s", journal_page)
            return journal_page
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

    def convert_client_page(self, result: Dict[str, Any]) -> JournalPage:
        try:
            api_journal_page = ApiJournalPage(**result)
            # Build client-facing properties using the typed dataclasses
            client_props = JournalProperties(
                Type=api_journal_page.properties.Type,
                Title=api_journal_page.properties.Title,
                Status=api_journal_page.properties.Status,
                Timeline=api_journal_page.properties.Timeline,
                Description=api_journal_page.properties.Description,
            )
            return JournalPage(
                Id=PageId(Id=api_journal_page.id),
                Icon=api_journal_page.icon,
                Properties=client_props
            )
        except ValidationError as e:
            raise RepositoryError(
                message=f"Failed to parse API response to JournalPage:'{e}'\n{result}"
            ) from e


@dataclass
class RepositoryDirectInjection:
    source_repo: NotionRepoSource
    journal_repo: NotionRepoJournal
