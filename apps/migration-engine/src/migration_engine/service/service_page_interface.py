from abc import ABC, abstractmethod
from typing import Generic, List

from common_libs.constants.literal_definitions import DatasourceInfo, JournalRelations
from common_libs.models.client_models import DB, K, P, R


class ServiceError(Exception):
    """Base Service Layer Error."""

class ServicePageInterface(Generic[K, P, DB, R], ABC):
    @abstractmethod
    async def read_page(self, page_id: K) -> P:
        pass

    @abstractmethod
    async def query_database(
        self, datasource_info: DatasourceInfo, datasource_type: DB, filter_query: dict
    ) -> List[P]:
        pass

    # pylint: disable=too-many-positional-arguments, too-many-arguments
    @abstractmethod
    async def build_page_hierarchy(
        self,
        root_page: P,
        source_datasource_info: DatasourceInfo,
        journal_datasource_info: DatasourceInfo,
        journal_relation: JournalRelations,
        level: int = 0,
    ) -> List[P]:
        pass

    @abstractmethod
    async def create_or_update_page(self, page: P) -> bool:
        pass

    @abstractmethod
    async def add_relations_to_page(self, page: P, relations: R) -> None:
        pass

    @abstractmethod
    async def remove_relations_from_page(self, page: P, relations: R) -> None:
        pass

    @abstractmethod
    async def migrate_page(
        self,
        page: P,
        source_datasource_info: DatasourceInfo,
        target_datasource_info: DatasourceInfo,
    ) -> None:
        pass

    @abstractmethod
    async def migrate_pages(
        self,
        pages: List[P],
        source_datasource_info: DatasourceInfo,
        target_datasource_info: DatasourceInfo,
    ) -> None:
        pass

    @abstractmethod
    async def verify_page_migration(self, page: P) -> bool:
        pass

    @abstractmethod
    async def migrate_all_pages(self) -> None:
        pass
