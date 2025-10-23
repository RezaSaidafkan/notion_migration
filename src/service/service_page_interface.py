
from typing import List, Union

from constants.literal_definitions import DatabaseName, JournalRelations
from src.models.client_models import CommonPage
from abc import ABC, abstractmethod

class ServicePageInterface(ABC):
    @abstractmethod
    def get_page(self, page_id: str) -> CommonPage:
        pass
    
    @abstractmethod
    def query_database(self, database_id: str, database_name: DatabaseName, filter: dict) -> List[CommonPage]:
        pass
    
    @abstractmethod
    def build_page_hierarchy(self,
                                   root_page: CommonPage, 
                                   source_database_id: str, 
                                   journal_database_id: str, 
                                   journal_relation: JournalRelations,
                                   level: int = 0) -> List[CommonPage]:
        pass
    
    @abstractmethod
    def create_or_update_page(self, page: CommonPage) -> CommonPage:
        pass
    
    @abstractmethod
    def add_relations_to_page(self, page: CommonPage, relations: List[str]) -> None:
        pass
    
    @abstractmethod
    def remove_relations_from_page(self, page: CommonPage, relations: List[str]) -> None:
        pass
    
    @abstractmethod
    def migrate_page(self, page: CommonPage, sourceDatabaseId: str, destinationDatabaseId: str) -> None:
        pass

    @abstractmethod
    def migrate_pages(self, pages: List[CommonPage], sourceDatabaseId: str, destinationDatabaseId: str) -> None:
        pass
    
    @abstractmethod
    def verify_page_migration(self, page_id: str) -> CommonPage:
        pass

    @abstractmethod
    def migrate_all_pages(self) -> None:
        pass
    