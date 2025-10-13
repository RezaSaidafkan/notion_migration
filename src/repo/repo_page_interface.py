from src.models.client_models import ClientPage, ClientPageProperties, ClientPageRelations
from typing import List, Dict, Any
from abc import ABC, abstractmethod

class RepoPageInterface(ABC):
    @abstractmethod
    async def get_page(self, page_id: str) -> ClientPage:
        pass

    @abstractmethod
    async def query_database(self, database_id: str, filter: Dict[str, Any] = None) -> List[ClientPage]:
        pass

    @abstractmethod
    async def create_page(self, parent: ClientPage, properties: ClientPageProperties, relations: ClientPageRelations = None) -> ClientPage:
        pass

    @abstractmethod # TODO: see if you can fix partial pass for dataclass properties
    async def update_page(self, page: ClientPage, properties: ClientPageProperties) -> ClientPage:
        pass

    @abstractmethod
    async def append_page_relations(self, page: ClientPage, relations: ClientPageRelations) -> None:
        pass