from dataclasses import dataclass
from constants.literal_definitions import DatabaseName
from src.models.client_models import CommonPage, PageProperties, PageRelation
from typing import List, Dict, Any, Union
from abc import ABC, abstractmethod


@dataclass
class PaginationResult:
    results: List[CommonPage]
    has_more: bool
    next_cursor: Union[str, None]


class RepoPageInterface(ABC):
    @abstractmethod
    async def get_page(self,         page_id: str,
        database_name: DatabaseName) -> CommonPage:
        pass

    @abstractmethod
    async def query_database(
                    self,
                    database_id: str,
                    database_name: DatabaseName,
                    page_size: int,
                    cursor: str,
                    debug: bool
                    ) -> PaginationResult:
        pass

    @abstractmethod
    async def create_page(self, parent: CommonPage, properties: PageProperties, relations: PageRelation = None) -> CommonPage:
        pass

    @abstractmethod # TODO: see if you can fix partial pass for dataclass properties
    async def update_page(self, page: CommonPage, properties: PageProperties) -> CommonPage:
        pass

    @abstractmethod
    async def append_page_relations(self, page: CommonPage, relations: PageRelation) -> None:
        pass