import logging
from abc import abstractmethod
from asyncio import Condition, Event
from dataclasses import dataclass
from logging import Logger
from typing import Any, Generic, List, Optional
from uuid import UUID

from common_libs.constants.literal_definitions import RelationDefinitions
from common_libs.models.api_models import ApiPage
from common_libs.models.client_models import (
    B,
    BasePage,
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
    retry,
    retry_if_exception_type,
    retry_if_not_exception_type,
    stop_after_attempt,
)
from tenacity.wait import wait_base

from migration_engine.repo.notion_object_mapping.notion_object_map import translate
from migration_engine.repo.repo_page_interface import (
    QueryType,
    RepositoryError,
    RepositoryInterface,
)

logger = logging.getLogger(__name__)
logger_client: Logger = logger.getChild("client")

ATTEMPT_TRIAL_NUMBER = 3
RETRY_TIMEOUT_FALLBACK = 3

EVENT = Event()
EVENT.set()
API_LOCK = Condition()
ACTIVE_CALL_ID: Optional[UUID] = None  # Tracking which call is allowed through the gate


# pylint: disable=invalid-name, too-few-public-methods
class wait_error_callback(wait_base):
    def __init__(self, retry_timeout_fallback: float) -> None:
        self._retry_timeout_fallback = retry_timeout_fallback

    def __call__(self, retry_state: RetryCallState) -> float:
        if retry_state.outcome:
            exception = retry_state.outcome.exception()
            if isinstance(exception, APIResponseError) and \
                exception.code == APIErrorCode.RateLimited:
                retry_timeout = exception.headers.get("Retry-After")
                logger.debug("Retring after '%d' seconds", float(retry_timeout))
                return float(retry_timeout)
        return self._retry_timeout_fallback

def handle_outcome(retry_state: RetryCallState):
    if retry_state.outcome:
        if retry_state.outcome.failed:
            EVENT.clear()
        else:
            EVENT.set()

# pylint: disable=unused-argument
def set_on_exhausted(retry_state: RetryCallState):
    EVENT.set()
    logger.debug("Retry loop exhausted, set EVENT to '%s'", repr(EVENT))


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
    Generic[B], RepositoryInterface[BasePage, B, RelationDefinitions], ClientSingleton):
    # pylint: disable=invalid-overridden-method
    async def read_page(self, page: BasePage, debug: bool=False) -> B:
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
    def convert_client_page(self, result: ApiPage) -> B:
        pass

    # pylint: disable=unused-argument, global-statement
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
        wait=wait_error_callback(RETRY_TIMEOUT_FALLBACK),
        after=handle_outcome,
        retry_error_callback=set_on_exhausted,
        stop=stop_after_attempt(ATTEMPT_TRIAL_NUMBER),
        )
    @rate_limited
    @tracer
    async def _query_notion(
        self,
        page: BasePage,
        execution_context: ExecutionContext,
        data_source_id: UUID,
        query: QueryType
    ) -> Any:
        global ACTIVE_CALL_ID  # noqa: PLW0603
        call_id = page.Id.Id

        async with API_LOCK:
            # If rate-limited, wait until this call becomes active
            while not EVENT.is_set() and ACTIVE_CALL_ID != call_id:
                if ACTIVE_CALL_ID is None:
                    ACTIVE_CALL_ID = call_id
                else:
                    # Another call is active, wait for it to finish
                    logger.debug("Stalled processing PageId '%s':\
                                  Another call is active, wait for it to finish", call_id)
                    await API_LOCK.wait()
                    continue

            try:
                # Now this call has the gate
                response: Any = None
                response = await self.notion.data_sources.query(str(data_source_id), **query)
                EVENT.set()
                return response
            finally:
                # Always clear active call and notify waiters, even on exception
                if ACTIVE_CALL_ID == call_id:
                    ACTIVE_CALL_ID = None
                    API_LOCK.notify_all()

    # pylint: disable=too-many-positional-arguments, too-many-arguments, too-many-locals
    @tracer
    async def query_database(
        self,
        page: BasePage,
        execution_context: ExecutionContext,
        data_source_id: UUID,
        relation: RelationDefinitions,
        cursor: str | None = None,
    ) -> PaginationResult[B]:

        query: QueryType = {}
        response: Any = None

        try:
            filter_query = translate(relation=relation, page=page)

            query["filter"] = filter_query if filter_query else {}
            query["page_size"] = execution_context.page_size
            if cursor:
                query["start_cursor"] = cursor

            # Gate new queries at the rate-limit event. Retry attempts inside _query_notion
            # are allowed to proceed - they are synchronized via API_LOCK.
            await EVENT.wait()

            response = await self._query_notion(page=page,
                                                execution_context=execution_context,
                                                data_source_id=data_source_id,
                                                query=query)

            if execution_context.debug:
                logger.debug(
                    "Successfully queried to Notion client with query '%s'",
                    query)

            results = [ApiPage(**result) for result in response["results"]]
            converted_results: List[B] = [
                self.convert_client_page(apiPage) for apiPage in results
            ]

            return PaginationResult[B](
                results=converted_results,
                has_more=response["has_more"],
                next_cursor=response.get("next_cursor"),
            )
        except KeyError as ke:
            raise RepositoryError(
                message = "Failed to parse API response to internal model",
                error_type = type(ke),
                query=query
            ) from None
        except ConnectError as c_e:
            raise RepositoryError(
                error_type=type(c_e),
                query=query
            ) from None
        except RequestTimeoutError as rto_e:
            raise RepositoryError(
                code = rto_e.code,
                error_type = type(rto_e),
                query = query) from None
        except APIResponseError as api_e:
            raise RepositoryError(
                code= api_e.code,
                status= api_e.status,
                error_type= type(api_e),
                query= query) from None
        except HTTPResponseError as hr_e:
            raise RepositoryError(
                code=hr_e.code,
                status=hr_e.status,
                error_type=type(hr_e),
                query=query) from None
        except ValidationError as validation_e:
            raise RepositoryError(
                message=validation_e.json(),
                error_type=type(validation_e),
                query=query
            ) from None
        except Exception as e:
            raise RepositoryError(
                error_type=type(e),
                message=str(e),
                query=query) from None

    async def create_page(self, page: B, debug: bool) -> bool:
        raise NotImplementedError(
            "Creating pages is not implemented in NotionClientAPI"
        )

    async def update_page(self, page: B, debug: bool) -> bool:
        raise NotImplementedError(
            "Updating pages is not implemented in NotionClientAPI"
        )


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
