from typing import List, Dict, Any
from src.models.client_models import ClientPage, ClientPageProperties, ClientPageRelations
from src.models.api_models import ApiPage
from notion_client import AsyncClient as Client
from src.repo.repo_page_interface import RepoPageInterface
    

class NotionClientAPI(RepoPageInterface):
    def __init__(self, notion_token: str):
        self.notion = Client(auth=notion_token)

    async def get_page(self, page_id: str) -> ClientPage:
        response = await self.notion.pages.retrieve(page_id=page_id)
        return page_domain_convert(ApiPage.from_dict(response))

    async def query_database(self, database_id: str, filter: Dict[str, Any] = None) -> List[ClientPage]:
        results = []
        has_more = True
        cursor = None
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
        converted_results = [page_domain_convert(apiPage) for apiPage in results]
        return converted_results

    async def create_page(self, database_id: str, pageProperties: ClientPageProperties, pageRelations: List[ClientPageRelations]) -> ClientPage:
        response = await self.notion.pages.create(
            **{
                "parent": {"database_id": database_id},
                "properties": pageProperties.to_json(),
                "children": [relation.to_json() for relation in pageRelations] or [],
            }
        )
        return page_domain_convert(ApiPage.from_dict(response))

    async def update_page(self, page: ClientPage, properties: Dict[str, Any]) -> ClientPage:
        raise NotImplementedError("Updating pages is not implemented in NotionClientAPI")

    async def append_page_relations(self, page: ClientPage, relations: ClientPageRelations) -> None:
        raise NotImplementedError("Appending relations is not implemented in NotionClientAPI")


def page_domain_convert(apiPage: ApiPage) -> ClientPage:
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
        # Ancestors=props.Ancestors,
        # Descendants=props.Descendants,
        # Journals=props.Journals,
    )

    # client_relations = ClientPageRelations(
    #     Journals=props.Journals,
    #     Ancestors=props.Ancestors,
    #     Descendants=props.Descendants,
    # )

    # return ClientPage(id=apiPage.id, icon=apiPage.icon, properties=client_props, relations=client_relations)
    return ClientPage(id=apiPage.id, icon=apiPage.icon, properties=client_props)
