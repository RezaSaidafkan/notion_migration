import pprint
from typing import List, Dict, Any, Union, Callable
from src.models.client_models import Page, JournalPage, CommonPage, PageProperties, PageRelation, JournalPageProperties
from src.models.api_models import ApiPage
from notion_client import AsyncClient as Client
from src.repo.repo_page_interface import PaginationResult, RepoPageInterface
from src.constants.literal_definitions import DatabaseName, JournalRelations, SourceRelations
from src.config.load_config import GLOBAL_CONFIG

class NotionClientAPI(RepoPageInterface):
    def __init__(self, notion_token: str):
        self.notion = Client(auth=notion_token)

    
    async def get_page(
        self,
        page_id: str,
        database_name: DatabaseName
        ) -> CommonPage:
        response = await self.notion.pages.retrieve(page_id=page_id)
        return domain_convert_client_page(database_name)(ApiPage.from_dict(response))

    async def query_database(
                    self,
                    database_id: str,
                    database_name: DatabaseName,
                    page_size: int,
                    cursor: str = None,
                    filter: Dict[str, Any] = None,
                    debug: bool = GLOBAL_CONFIG.DEBUG
                    ) -> PaginationResult:
        results = []
        has_more = True
        try:
            while has_more:
                query = {
                        "database_id": database_id,
                        "start_cursor": cursor,
                        "filter": filter or {},
                        "page_size": page_size,
                    }
                pprint.pprint(query)
                resp = await self.notion.databases.query(**query)
                results.extend([ApiPage.from_dict(result) for result in resp["results"]])
                has_more = resp["has_more"]
                cursor = resp.get("next_cursor")
                if debug:
                    print(f"Fetched {len(results)} pages so far...")
            converted_results = [domain_convert_client_page(database_name)(apiPage) for apiPage in results]
            return PaginationResult(results=converted_results, has_more=has_more, next_cursor=cursor)
        except Exception as e:
            print(f"Error querying database {database_id}: {e}")
            return PaginationResult(results=[], has_more=False, next_cursor=None)

    async def create_page(self, database_id: str, pageProperties: PageProperties, pageRelations: PageRelation) -> CommonPage:
        raise NotImplementedError("Creating pages is not implemented in NotionClientAPI")

    async def update_page(self, page: CommonPage, properties: Dict[str, Any]) -> CommonPage:
        raise NotImplementedError("Updating pages is not implemented in NotionClientAPI")

    async def append_page_relations(self, page: CommonPage, relations: PageRelation) -> None:
        raise NotImplementedError("Appending relations is not implemented in NotionClientAPI")


def domain_convert_client_source_page(apiPage: ApiPage) -> CommonPage:
    props = apiPage.properties

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
    return CommonPage(Id=apiPage.id, Icon=apiPage.icon, Properties=client_props)

def domain_convert_client_journal_page(apiPage: ApiPage) -> JournalPage:
    props = apiPage.properties

    # Build client-facing properties using the typed dataclasses
    client_props = JournalPageProperties(
        Type=props.Type,
        Title=props.Title,
        Status=props.Status,
        Timeline=props.Timeline,
        Description=props.Description
    )
    return JournalPage(Id=apiPage.id, Icon=apiPage.icon, Properties=client_props)

def domain_convert_client_page(database_name: DatabaseName) -> Callable[[ApiPage], Union[Page, JournalPage]]:
        if database_name == DatabaseName.SOURCE:
            return domain_convert_client_source_page
        else:
            return domain_convert_client_journal_page
