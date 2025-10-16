from typing import List, Dict, Any, Union, Callable
from src.models.client_models import ClientJournalPage, ClientPage, ClientPageProperties, ClientRelation, JournalPageProperties
from src.models.api_models import ApiPage
from notion_client import AsyncClient as Client
from src.repo.repo_page_interface import RepoPageInterface
from src.constants.literal_definitions import DatabaseName, JournalName

class NotionClientAPI(RepoPageInterface):
    def __init__(self, notion_token: str):
        self.notion = Client(auth=notion_token)

    
    async def get_page(self, page_id: str, database: DatabaseName) -> ClientPage:
        response = await self.notion.pages.retrieve(page_id=page_id)
        return domain_convert_client_page(database)(ApiPage.from_dict(response))

    async def query_database(self, database_id: str, database: Union[DatabaseName, JournalName], filter: Dict[str, Any] = None) -> List[ClientPage]:
        results = []
        has_more = True
        cursor = None
        try:
            while has_more:
                resp = await self.notion.databases.query(
                    **{
                        "database_id": database_id,
                        "start_cursor": cursor,
                        "filter": filter or {},
                        "page_size": 100,
                    }
                )
                results.extend([ApiPage.from_dict(result) for result in resp["results"]])
                has_more = resp["has_more"]
                cursor = resp.get("next_cursor")
            converted_results = [domain_convert_client_page(database)(apiPage) for apiPage in results]
            return converted_results
        except Exception as e:
            print(f"Error querying database {database_id}: {e}")
            return []

    async def create_page(self, database_id: str, pageProperties: ClientPageProperties, pageRelations: ClientRelation) -> ClientPage:
        raise NotImplementedError("Creating pages is not implemented in NotionClientAPI")

    async def update_page(self, page: ClientPage, properties: Dict[str, Any]) -> ClientPage:
        raise NotImplementedError("Updating pages is not implemented in NotionClientAPI")

    async def append_page_relations(self, page: ClientPage, relations: ClientRelation) -> None:
        raise NotImplementedError("Appending relations is not implemented in NotionClientAPI")


def domain_convert_client_source_page(apiPage: ApiPage) -> ClientPage:
    props = apiPage.properties

    # Build client-facing properties using the typed dataclasses
    client_props = ClientPageProperties(
        Type=props.Type,
        Title=props.Title,
        Assignee=props.Assignee,
        Priority=props.Priority,
        Urgency=props.Urgency,
        Status=props.Status,
        Timeline=props.Timeline,
        Description=props.Description,
        
    )
    return ClientPage(id=apiPage.id, icon=apiPage.icon, properties=client_props)

def domain_convert_client_journal_page(apiPage: ApiPage) -> ClientJournalPage:
    props = apiPage.properties

    # Build client-facing properties using the typed dataclasses
    client_props = JournalPageProperties(
        Title=props.Title,
        Date=props.Timeline,
        Description=props.Description
    )
    return ClientJournalPage(id=apiPage.id, icon=apiPage.icon, properties=client_props)

def domain_convert_client_page(database: Union[DatabaseName, JournalName]) -> Callable[[ApiPage], Union[ClientPage, ClientJournalPage]]:
        if database == DatabaseName:
            return domain_convert_client_source_page
        else:
            return domain_convert_client_journal_page
