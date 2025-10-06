from typing import List, Dict, Any 
from src.models.client_models import ClientPage, ClientPage, ClientPageProperties, ClientPageRelations
from src.models.api_models import ApiPage
from notion_client import Client
from src.repo.repo_page_interface import RepoPageInterface
    

class NotionClientAPI(RepoPageInterface):
    def __init__(self, notion_token: str):
        self.notion = Client(auth=notion_token)
    
    def get_page(self, page_id: str) -> ClientPage:
        response = self.notion.pages.retrieve(page_id=page_id)
        return page_domain_convert(response)

    def query_database(self, database_id: str, filter: Dict[str, Any] = None) -> List[ClientPage]:
        results = []
        has_more = True
        cursor = None
        while has_more:
            resp = self.notion.databases.query(
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

    def create_page(self, database_id: str, pageProperties: ClientPageProperties, pageRelations: List[ClientPageRelations]) -> ClientPage:
        response = self.notion.pages.create(
            **{
                "parent": {"database_id": database_id},
                "properties": pageProperties.to_json(),
                "children": [relation.to_json() for relation in pageRelations] or [],
            }
        )
        return page_domain_convert(ApiPage.from_dict(response))

    def update_page(self, page_id: str, properties: Dict[str, Any]) -> ClientPage:
        raise NotImplementedError("Updating pages is not implemented in NotionClientAPI")

    def append_page_relations(self, page_id: str, relations: List[str]) -> None:
        raise NotImplementedError("Appending relations is not implemented in NotionClientAPI")


def page_domain_convert(apiPage: ApiPage) -> ClientPage:
    relations = [] 
    if apiPage.properties.Ancestors:
        relations.extend(apiPage.properties.Ancestors)
    if apiPage.properties.Descendants:
        relations.extend(apiPage.properties.Descendants)
    if apiPage.properties.Journals:
        relations.extend(apiPage.properties.Journals)
    properties = apiPage.to_dict()
    properties.pop("id", None)
    properties.pop("icon", None)
    properties.pop("Ancestors", None)
    properties.pop("Descendants", None)
    properties.pop("Journals", None)
    return ClientPage(id=apiPage.id, icon=apiPage.icon, properties=properties, relations=relations)
