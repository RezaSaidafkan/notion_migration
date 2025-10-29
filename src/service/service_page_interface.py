from typing import List, Coroutine, Generic
from src.constants.literal_definitions import JournalRelations, DatabaseInfo
from src.models.client_models import P, K, DB, R
from abc import ABC, abstractmethod


class ServicePageInterface(Generic[K, P, DB, R], ABC):
    @abstractmethod
    def refresh_from_backend(
        self, page_id: K
    ) -> Coroutine[None, None, P]:
        pass

    @abstractmethod
    async def query_database(
        self, database_info: DatabaseInfo, database_type: DB, filter: dict
    ) -> List[P]:
        pass

    @abstractmethod
    async def build_page_hierarchy(
        self,
        root_page: P,
        source_database_info: DatabaseInfo,
        journal_database_nfo: DatabaseInfo,
        journal_relation: JournalRelations,
        level: int = 0,
    ) -> List[P]:
        pass

    @abstractmethod
    async def create_or_update_page(self, page: P) -> bool:
        pass

    @abstractmethod
    async def add_relations_to_page(
        self, page: P, relations: R
    ) -> None:
        pass

    @abstractmethod
    async def remove_relations_from_page(
        self, page: P, relations: R
    ) -> None:
        pass

    @abstractmethod
    async def migrate_page(
        self, page: P, source_database_info: DatabaseInfo, destination_database_info: DatabaseInfo
    ) -> None:
        pass

    @abstractmethod
    async def migrate_pages(
        self, pages: List[P], source_database_info: DatabaseInfo, destination_database_info: DatabaseInfo
    ) -> None:
        pass

    @abstractmethod
    async def verify_page_migration(self, page: P) -> bool:
        pass

    @abstractmethod
    async def migrate_all_pages(self) -> None:
        pass
