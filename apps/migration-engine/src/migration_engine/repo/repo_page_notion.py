import logging
from abc import abstractmethod
from typing import Any, Dict, Generic, List
from uuid import UUID

from common_libs.constants.literal_definitions import ExecutionContext
from common_libs.models.api_models import ApiPage
from common_libs.models.client_models import (
    JournalPage,
    JournalPageProperties,
    P,
    Page,
    PageId,
    PageProperties,
    PaginationResult,
)
from notion_client import APIResponseError
from notion_client import AsyncClient as Client
from pydantic import ValidationError

from migration_engine.repo.repo_page_interface import (
    RepositoryError,
    RepositoryInterface,
)
from migration_engine.utils.rate_limiter import rate_limited

logger = logging.getLogger(__name__)


# pylint: disable=too-few-public-methods
class ClientSingleton:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, notion_token: str, debug: bool):
        self.notion = Client(auth=notion_token,
                             logger=logger,
                             log_level=logging.DEBUG if debug else logging.INFO)


class NotionRepository(
    Generic[P], RepositoryInterface[PageId, P, PaginationResult[P]], ClientSingleton
):
    async def read_page(self, page_id: PageId, debug: bool=False) -> P:
        try:
            raw_result = await self.notion.pages.retrieve(page_id=str(page_id.Id))
            api_page = ApiPage(**raw_result)
            page: P = self.convert_client_page(api_page)
            return page
        except APIResponseError as ae:
            logger.exception(ae)
            raise RepositoryError(
                f"Failed to retrieve page {page_id}") from ae
        except ValidationError as ve:
            logger.exception(ve)
            raise RepositoryError(
                f"Failed to validate response with the model for page {page_id}") from ve
        except Exception as e:
            logger.exception("Unknown error happend")
            raise RepositoryError("Unknown error happend") from e

    @abstractmethod
    def convert_client_page(self, result: ApiPage) -> P:
        pass

    # pylint: disable=too-many-positional-arguments, too-many-arguments
    @rate_limited(max_rate=3, time_period=1)
    async def query_database(
        self,
        data_source_id: UUID,
        filter_query: Dict[str, Any],
        execution_context: ExecutionContext,
        cursor: str | None = None
    ) -> PaginationResult[P]:
        try:
            query = {
                "start_cursor": cursor,
                "filter": filter_query or {},
                "page_size": execution_context.PAGE_SIZE,
            }
            resp = await self.notion.data_sources.query(str(data_source_id), **query)

            if execution_context.DEBUG:
                logger.debug(
                    "Query to Notion CLient:\n%s\nResponse from Notion Client:\n%s", query, resp)

            results = [ApiPage(**result) for result in resp["results"]]
            converted_results: List[P] = [
                self.convert_client_page(apiPage) for apiPage in results
            ]
            return PaginationResult[P](
                results=converted_results,
                has_more=resp["has_more"],
                next_cursor=resp.get("next_cursor"),
            )
        except KeyError as key_error:
            logging.exception("Failed to parse API response to internal model:\n%s\n%s",
                              key_error, resp)
            raise RepositoryError(
                f"Failed to parse API response to internal model:\n{key_error}\n{resp}"
            ) from key_error
        except APIResponseError as e:
            logging.exception("Failed to query with:\n%s\n%s", query, e)
            raise RepositoryError(
                f"Failed to query API with:\n{query}") from e
        except ValidationError as e:
            logging.exception("Failed to query with:\n%s\n%s", query, e)
            raise RepositoryError(
                f"Failed to validate response with the model for query:\n{query}") from e
        except Exception as e:
            logging.exception("Unknown error happend for:\n%s\n%s", query, e)
            raise RepositoryError(f"Unknown error happend for:\n{query}") from e

    async def create_page(self, page: P, debug: bool) -> bool:
        raise NotImplementedError(
            "Creating pages is not implemented in NotionClientAPI"
        )

    async def update_page(self, page: P, debug: bool) -> bool:
        raise NotImplementedError(
            "Updating pages is not implemented in NotionClientAPI"
        )


class NotionRepoPage(NotionRepository[Page]):
    def convert_client_page(self, result: ApiPage) -> Page:
        try:
            props = result.properties
            # Build client-facing properties using the typed dataclasses
            client_props = PageProperties(
                Type=props.Type,
                Title=props.Title,
                Assignee=props.Assignee,
                Priority=props.Priority,
                Urgency=props.Urgency,
                Status=props.Status,
                Timeline=props.Timeline,
                Description=props.Description,
            )
            return Page(
                Id=PageId(Id=result.id), Icon=result.icon, Properties=client_props
            )
        except ValidationError as e:
            raise RepositoryError(
                f"Failed to parse API response to Page:\n{e}\n{result}"
            ) from e


class NotionRepoJournalPage(NotionRepository[JournalPage]):
    def convert_client_page(self, result: ApiPage) -> JournalPage:
        try:
            props = result.properties

            # Build client-facing properties using the typed dataclasses
            client_props = JournalPageProperties(
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
                f"Failed to parse API response to JournalPage:\n{e}\n{result}"
            ) from e
