
from typing import List
from src.models.client_models import ClientPage
from abc import ABC, abstractmethod

class ServicePageInterface(ABC):
    @abstractmethod
    def get_page(self, page_id: str) -> ClientPage:
        pass
    
    @abstractmethod
    def build_page_hierarchy(self, parent_page: ClientPage, database_id: str) -> None:
        pass
    
    @abstractmethod
    def create_or_update_page(self, page: ClientPage) -> ClientPage:
        pass
    
    @abstractmethod
    def create_page_hierarchy(self, parent_id: str, properties: dict, children: List[dict]) -> ClientPage:
        pass
    
    @abstractmethod
    def add_relations_to_page(self, page: ClientPage, relations: List[str]) -> None:
        pass
    
    @abstractmethod
    def remove_relations_from_page(self, page: ClientPage, relations: List[str]) -> None:
        pass
    
    @abstractmethod
    def migrate_page(self, page_id: str) -> None:
        pass

    @abstractmethod
    def migrate_pages(self, page_ids: List[str]) -> None:
        pass

    @abstractmethod
    def migrate_all_pages(self) -> None:
        pass
    
    @abstractmethod
    def verify_page_migration(self, page_id: str) -> ClientPage:
        pass
    