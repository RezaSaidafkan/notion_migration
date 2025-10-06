from typing import List

from src.service.service_page_interface import ServicePageInterface
from src.repo.repo_page_interface import RepoPageInterface
from src.models.client_models import ClientPage


class ServicePage(ServicePageInterface):
    """Service layer for page-related domain logic.

    Keep schema- and business-logic here. The repository should expose
    generic persistence queries (like `query_database`) without hardcoding
    domain property names.
    """

    def __init__(self, repo: RepoPageInterface) -> None:
        self._repo = repo
        
    def get_page(self, page_id: str) -> ClientPage:
        raise NotImplementedError("This method should be implemented in the repository layer.")
    
    def get_descendants_of_parent(self, parent_page_id: str, database_id: str) -> List[ClientPage]:
        """Return pages whose 'Ancestor' relation contains the given parent.

        This method contains the schema knowledge ('Ancestor' relation) and
        delegates to the repository's generic `query_database` method.
        """
        return self._repo.query_database(
            database_id=database_id,
            filter={
                "property": "Ancestors",
                "relation": {"contains": parent_page_id},
            },
        )

    def get_page_hierarchy(self, page_id: str) -> dict:
        raise NotImplementedError("This method should be implemented in the repository layer.")
    
    def create_or_update_page(self, page: ClientPage) -> ClientPage:
        raise NotImplementedError("This method should be implemented in the repository layer.")
    
    def create_page_hierarchy(self, parent_id: str, properties: dict, children: List[dict]) -> ClientPage:
        raise NotImplementedError("This method should be implemented in the repository layer.")
    
    def add_relations_to_page(self, page: ClientPage, relations: List[str]) -> None:
        raise NotImplementedError("This method should be implemented in the repository layer.")
    
    def remove_relations_from_page(self, page: ClientPage, relations: List[str]) -> None:
        raise NotImplementedError("This method should be implemented in the repository layer.")
    
    def migrate_page(self, page_id: str) -> None:
        raise NotImplementedError("This method should be implemented in the repository layer.")
    
    def migrate_pages(self, page_ids: List[str]) -> None:
        raise NotImplementedError("This method should be implemented in the repository layer.")
    
    def migrate_all_pages(self) -> None:
        raise NotImplementedError("This method should be implemented in the repository layer.")
    
    def verify_page_migration(self, page_id: str) -> ClientPage:
        raise NotImplementedError("This method should be implemented in the repository layer.")
    