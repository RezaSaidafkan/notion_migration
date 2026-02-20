import logging
from abc import abstractmethod
from dataclasses import dataclass
from typing import Generic, List
from uuid import UUID

from common_libs.constants.literal_definitions import RelationDefinitions
from common_libs.models.api_models import ApiPage
from common_libs.models.client_models import (
    B,
    JournalPage,
    JournalProperties,
    PageId,
    PaginationResult,
    TaskPage,
    TaskProperties,
)
from common_libs.models.context import ExecutionContext
from common_libs.utils.tracing import Tracing
from notion_client import APIResponseError
from notion_client import AsyncClient as Client
from pydantic import ValidationError

from migration_engine.repo.notion_object_mapping.notion_object_map import translate
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
    Generic[B], RepositoryInterface[PageId, B, RelationDefinitions], ClientSingleton
):
    async def read_page(self, page_id: PageId, debug: bool=False) -> B:
        try:
            raw_result = await self.notion.pages.retrieve(page_id=str(page_id.Id))
            api_page = ApiPage(**raw_result)
            page = self.convert_client_page(api_page)
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
    def convert_client_page(self, result: ApiPage) -> B:
        pass

    # pylint: disable=too-many-positional-arguments, too-many-arguments
    @rate_limited(max_rate=3, time_period=1)
    @Tracing("127.0.0.1", 8000)
    async def query_database(
        self,
        page_id: PageId,
        execution_context: ExecutionContext,
        data_source_id: UUID,
        relation: RelationDefinitions,
        cursor: str | None = None
    ) -> PaginationResult[B]:
        try:
            filter_query = translate(relation=relation, page_id=page_id)
            query = {
                "start_cursor": cursor,
                "filter": filter_query or {},
                "page_size": execution_context.page_size,
            }
            resp = await self.notion.data_sources.query(str(data_source_id), **query)

            if execution_context.debug:
                logger.debug(
                    "Query to Notion CLient:\n%s\nReceived Response from Notion Client", query)

            results = [ApiPage(**result) for result in resp["results"]]
            converted_results: List[B] = [
                self.convert_client_page(apiPage) for apiPage in results
            ]

            return PaginationResult[B](
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
        except APIResponseError as api_e:
            logging.exception("Failed to query with:\n%s\n%s", query, api_e)
            raise RepositoryError(
                f"Failed to query API with:\n{query}") from api_e
        except ValidationError as validation_e:
            logging.exception("Failed to query with:\n%s\n%s", query, validation_e)
            raise RepositoryError(
                f"Failed to validate response with the model for query:\n{query}") from validation_e
        except Exception as e:
            logging.exception("Unknown error happend for:\n%s\n%s", query, e)
            raise RepositoryError(f"Unknown error happend for:\n{query}") from e

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
                f"Failed to parse API response to Page:\n{e}\n{result}"
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
                f"Failed to parse API response to JournalPage:\n{e}\n{result}"
            ) from e


@dataclass
class RepositoryDirectInjection:
    source_repo: NotionRepoSource
    journal_repo: NotionRepoJournal
