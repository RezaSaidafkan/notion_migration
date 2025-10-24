from typing import List, Dict, Any, Generic
from src.models.client_models import (
    Page,
    JournalPage,
    PageProperties,
    JournalPageProperties,
    PaginationResult,
    T,
    PageId,
)
from src.models.api_models import ApiPage
from notion_client import AsyncClient as Client
from src.repo.repo_page_interface import RepositoryInterface
from src.config.load_config import GLOBAL_CONFIG
from abc import abstractmethod


class ClientSingleton:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, notion_token: str):
        self.notion = Client(auth=notion_token)


class NotionRepository(
    Generic[T], RepositoryInterface[PageId, T, PaginationResult[T]], ClientSingleton
):
    def __init__(self, notion_token: str):
        super().__init__(notion_token)

    async def read_page(self, page_id: PageId, debug: bool = False) -> T:
        raw_result = await self.notion.pages.retrieve(page_id=page_id.Id)
        api_page = ApiPage.from_dict(raw_result)
        page: T = self.convert_client_page(api_page)
        return page

    @abstractmethod
    def convert_client_page(self, result: ApiPage) -> T:
        pass

    async def query_database(
        self,
        database_id: str,
        page_size: int,
        filter: Dict[str, Any],
        cursor: str | None = None,
        debug: bool = GLOBAL_CONFIG.DEBUG,
    ) -> PaginationResult[T]:
        results = []
        has_more = True
        try:
            while has_more:
                query = {
                    "start_cursor": cursor,
                    "filter": filter or {},
                    "page_size": page_size,
                }
                resp = await self.notion.databases.query(database_id, **query)
                results.extend(
                    [ApiPage.from_dict(result) for result in resp["results"]]
                )
                has_more = resp["has_more"]
                cursor = resp.get("next_cursor")
                if debug:
                    print(f"Fetched {len(results)} pages so far...")
            converted_results: List[T] = [
                self.convert_client_page(apiPage) for apiPage in results
            ]
            return PaginationResult[T](
                results=converted_results, has_more=has_more, next_cursor=cursor
            )
        except Exception as e:
            print(f"Error querying database {database_id}: {e}")
            return PaginationResult[T](results=[], has_more=False, next_cursor=None)

    async def create_page(self, page: T, debug: bool) -> bool:
        raise NotImplementedError(
            "Creating pages is not implemented in NotionClientAPI"
        )

    async def update_page(self, page: T, debug: bool) -> bool:
        raise NotImplementedError(
            "Updating pages is not implemented in NotionClientAPI"
        )


class NotionRepoPage(NotionRepository[Page]):
    def __init__(self, notion_token: str):
        super().__init__(notion_token)

    def convert_client_page(self, result: ApiPage) -> Page:
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


class NotionRepoJournalPage(NotionRepository[JournalPage]):
    def __init__(self, notion_token: str):
        super().__init__(notion_token)

    def convert_client_page(self, result: ApiPage) -> JournalPage:
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
