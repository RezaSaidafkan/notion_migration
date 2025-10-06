from src.models.client_models import ClientPage, ClientPageProperties, ClientPageRelations
from typing import List, Dict, Any
from abc import ABC, abstractmethod

class RepoPageInterface(ABC):
    @abstractmethod
    def get_page(self, page_id: str) -> ClientPage:
        pass

    @abstractmethod
    def query_database(self, database_id: str, filter: Dict[str, Any] = None) -> List[ClientPage]:
        pass

    @abstractmethod
    def create_page(self, parent: ClientPage, properties: ClientPageProperties, relations: List[ClientPageRelations] = None) -> ClientPage:
        pass

    @abstractmethod # TODO: see if you can fix partial pass for dataclass properties
    def update_page(self, page: ClientPage, properties: ClientPageProperties) -> ClientPage:
        pass

    @abstractmethod
    def append_page_relations(self, page: ClientPage, relations: List[ClientPageRelations]) -> None:
        pass