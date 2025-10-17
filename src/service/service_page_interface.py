
from typing import List, Union

from constants.literal_definitions import DatabaseName, JournalName
from src.models.client_models import ClientPage
from abc import ABC, abstractmethod

class ServicePageInterface(ABC):
    @abstractmethod
    def get_page(self, page_id: str) -> ClientPage:
        pass
    
    @abstractmethod
    def query_database(self, database_id: str, database: Union[DatabaseName, JournalName], filter: dict) -> List[ClientPage]:
        pass
    
    @abstractmethod
    def build_page_hierarchy(self, parent_page: ClientPage, database_id: str) -> List[ClientPage]:
        pass
    
    @abstractmethod
    def create_or_update_page(self, page: ClientPage) -> ClientPage:
        pass
    
    @abstractmethod
    def add_relations_to_page(self, page: ClientPage, relations: List[str]) -> None:
        pass
    
    @abstractmethod
    def remove_relations_from_page(self, page: ClientPage, relations: List[str]) -> None:
        pass
    
    @abstractmethod
    def migrate_page(self, page: ClientPage, sourceDatabaseId: str, destinationDatabaseId: str) -> None:
        pass

    @abstractmethod
    def migrate_pages(self, pages: List[ClientPage], sourceDatabaseId: str, destinationDatabaseId: str) -> None:
        pass
    
    @abstractmethod
    def verify_page_migration(self, page_id: str) -> ClientPage:
        pass

    @abstractmethod
    def migrate_all_pages(self) -> None:
        pass
    