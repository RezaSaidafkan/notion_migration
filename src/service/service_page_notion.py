from typing import Generator, List

from src.service.service_page_interface import ServicePageInterface
from src.repo.repo_page_interface import RepoPageInterface
from src.models.client_models import ClientPage, ClientPageRelations


class ServicePage(ServicePageInterface):
    """Service layer for page-related domain logic.

    Keep schema- and business-logic here. The repository should expose
    generic persistence queries (like `query_database`) without hardcoding
    domain property names.
    """

    def __init__(self, repo: RepoPageInterface) -> None:
        self._repo = repo
        
    def get_page(self, page_id: str) -> ClientPage:
        return self._repo.get_page(page_id)

    def build_page_hierarchy(self, page: ClientPage, source_database_id: str, journal_database_id: str, journal_db_relation: str, level: int = 0) -> Generator[ClientPage, None, None]:
        """Return pages whose 'Ancestor' relation contains the given parent.

        This method contains the schema knowledge ('Ancestor' relation) and
        delegates to the repository's generic `query_database` method.
        """
        sub_pages = self._repo.query_database(
            database_id=source_database_id,
            filter={
                "property": "Ancestors",
                "relation": {"contains": page.id},
            },
        )
        
        journal_pages = self._repo.query_database(
            database_id=journal_database_id,
            filter={
                "property": journal_db_relation,
                "relation": {"contains": page.id},
            },
        )
        
        page.relations = ClientPageRelations(Descendants=None, Ancestors=None, Journals=None)
        
        if journal_pages:
            page.relations.Journals=journal_pages
        
        if sub_pages:
            # refresh the relations on the parent page to include the fetched children
            page.relations.Descendants=sub_pages
            for sub_page in sub_pages:
                yield from self.build_page_hierarchy(sub_page, source_database_id=source_database_id, journal_database_id=journal_database_id, journal_db_relation=journal_db_relation, level=level + 1)
        if level == 1:
            yield page

    def create_or_update_page(self, page: ClientPage) -> ClientPage:
        raise NotImplementedError("This method should be implemented in the service layer.")
    
    def add_relations_to_page(self, page: ClientPage, relations: List[str]) -> None:
        raise NotImplementedError("This method should be implemented in the service layer.")
    
    def remove_relations_from_page(self, page: ClientPage, relations: List[str]) -> None:
        raise NotImplementedError("This method should be implemented in the service layer.")

    def migrate_page(self, page: ClientPage, sourceDatabaseId: str, destinationDatabaseId: str) -> None:
        raise NotImplementedError("This method should be implemented in the service layer.")

    def migrate_pages(self, pages: List[ClientPage], sourceDatabaseId: str, destinationDatabaseId: str) -> None:
        raise NotImplementedError("This method should be implemented in the service layer.")

    def verify_page_migration(self, page: ClientPage) -> ClientPage:
        raise NotImplementedError("This method should be implemented in the service layer.")

    def migrate_all_pages(self) -> None:
        raise NotImplementedError("This method should be implemented in the service layer.")
    