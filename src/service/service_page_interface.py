from typing import List, Coroutine, Type, Generic
from src.constants.literal_definitions import JournalRelations, DatabaseInfo
from src.models.client_models import CommonPage, T, PageId
from abc import ABC, abstractmethod


class ServicePageInterface(Generic[T], ABC):
    @abstractmethod
    def refresh_from_backend(
        self, page_id: PageId
    ) -> Coroutine[None, None, CommonPage]:
        pass

    @abstractmethod
    async def query_database(
        self, database_info: DatabaseInfo, database_type: Type[T], filter: dict
    ) -> List[T]:
        pass

    @abstractmethod
    async def build_page_hierarchy(
        self,
        root_page: T,
        source_database: DatabaseInfo,
        journal_database: DatabaseInfo,
        journal_relation: JournalRelations,
        level: int = 0,
    ) -> List[T]:
        pass

    @abstractmethod
    async def create_or_update_page(self, page: CommonPage) -> CommonPage:
        pass

    @abstractmethod
    async def add_relations_to_page(
        self, page: CommonPage, relations: List[str]
    ) -> None:
        pass

    @abstractmethod
    async def remove_relations_from_page(
        self, page: CommonPage, relations: List[str]
    ) -> None:
        pass

    @abstractmethod
    async def migrate_page(
        self, page: CommonPage, sourceDatabaseId: str, destinationDatabaseId: str
    ) -> None:
        pass

    @abstractmethod
    async def migrate_pages(
        self, pages: List[CommonPage], sourceDatabaseId: str, destinationDatabaseId: str
    ) -> None:
        pass

    @abstractmethod
    async def verify_page_migration(self, page: CommonPage) -> bool:
        pass

    @abstractmethod
    async def migrate_all_pages(self) -> None:
        pass
