from typing import List, Dict, Any, Generic, Coroutine
from src.models.client_models import (
    Page,
    JournalPage,
    PageProperties,
    JournalPageProperties,
    PaginationResult,
    P,
    PageId,
)
from src.models.api_models import ApiPage
from notion_client import AsyncClient as Client,    APIResponseError
from src.repo.repo_page_interface import RepositoryInterface
from src.config.load_config import GLOBAL_CONFIG
from abc import abstractmethod
import asyncio
import logging


class RepositoryError(Exception):
    pass


# --- Global Rate Limiting ---
# A single semaphore for all repository instances to ensure we don't exceed Notion's API rate limit.
SEMAPHORE = asyncio.Semaphore(GLOBAL_CONFIG.SEMAPHORE_LIMIT)

async def _rate_limited(coro: Coroutine) -> Any:
    """Ensures all API calls are rate-limited."""
    async with SEMAPHORE:
        # Spacing out requests to stay under Notion's ~3 RPS limit.
        await asyncio.sleep(0.35)
        return await coro


class ClientSingleton:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, notion_token: str):
        self.notion = Client(auth=notion_token,  log_level=logging.DEBUG)


class NotionRepository(
    Generic[P], RepositoryInterface[PageId, P, PaginationResult[P]], ClientSingleton
):
    def __init__(self, notion_token: str):
        super().__init__(notion_token)

    async def read_page(self, page_id: PageId, debug: bool = False) -> P:
        try:
            raw_result = await _rate_limited(self.notion.pages.retrieve(page_id=page_id.Id))
            api_page = ApiPage(**raw_result)
            page: P = self.convert_client_page(api_page)
            return page
        except APIResponseError as e:
            raise RuntimeError(e)

    @abstractmethod
    def convert_client_page(self, result: ApiPage) -> P:
        pass

    async def query_database(
        self,
        data_source_id: str,
        page_size: int,
        filter: Dict[str, Any],
        cursor: str | None = None,
        debug: bool = GLOBAL_CONFIG.DEBUG,
    ) -> PaginationResult[P]:
        try:
            query = {
                "start_cursor": cursor,
                "filter": filter or {},
                "page_size": page_size,
            }
            resp = await _rate_limited(self.notion.data_sources.query(data_source_id, **query))

            results = [ApiPage(**result) for result in resp["results"]]
            converted_results: List[P] = [
                self.convert_client_page(apiPage) for apiPage in results
            ]
            return PaginationResult[P](
                results=converted_results,
                has_more=resp["has_more"],
                next_cursor=resp.get("next_cursor"),
            )
        except KeyError as keyError:
            raise RepositoryError(f"Failed to parse API response to internal model:\n{keyError}\n{resp}")
        except Exception as e:
            raise RepositoryError(e)

    async def create_page(self, page: P, debug: bool) -> bool:
        raise NotImplementedError(
            "Creating pages is not implemented in NotionClientAPI"
        )

    async def update_page(self, page: P, debug: bool) -> bool:
        raise NotImplementedError(
            "Updating pages is not implemented in NotionClientAPI"
        )


class NotionRepoPage(NotionRepository[Page]):
    def __init__(self, notion_token: str):
        super().__init__(notion_token)

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
            return Page(Id=PageId(Id=result.id), Icon=result.icon, Properties=client_props)
        except Exception as e:
            raise RepositoryError(f"Failed to parse API response to Page:\n{e}\n{result}")


class NotionRepoJournalPage(NotionRepository[JournalPage]):
    def __init__(self, notion_token: str):
        super().__init__(notion_token)

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
        except Exception as e:
            raise RepositoryError(f"Failed to parse API response to JournalPage:\n{e}\n{result}")
