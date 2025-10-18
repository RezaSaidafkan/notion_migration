from dataclasses import dataclass
from constants.literal_definitions import DatabaseName, JournalName
from src.models.client_models import ClientPage, ClientPageProperties, ClientRelation
from typing import List, Dict, Any, Union
from abc import ABC, abstractmethod


@dataclass
class PaginationResult:
    results: List[ClientPage]
    has_more: bool
    next_cursor: Union[str, None]


class RepoPageInterface(ABC):
    @abstractmethod
    async def get_page(self, page_id: str, database: DatabaseName) -> ClientPage:
        pass

    @abstractmethod
    async def query_database(self, database_id: str, database: Union[DatabaseName, JournalName], filter: Dict[str, Any] = None, cursor: Union[str, None] = None) -> List[ClientPage]:
        pass

    @abstractmethod
    async def create_page(self, parent: ClientPage, properties: ClientPageProperties, relations: ClientRelation = None) -> ClientPage:
        pass

    @abstractmethod # TODO: see if you can fix partial pass for dataclass properties
    async def update_page(self, page: ClientPage, properties: ClientPageProperties) -> ClientPage:
        pass

    @abstractmethod
    async def append_page_relations(self, page: ClientPage, relations: ClientRelation) -> None:
        pass