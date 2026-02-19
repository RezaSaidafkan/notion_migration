import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, List, Sequence

from common_libs.constants.literal_definitions import ExecutionContext
from common_libs.models.client_models import (
    RD,
    B,
    DatasourceInfo,
    J_co,
    K,
    MigrationContext,
    P_co,
    R,
)


class ServiceError(Exception):
    """Base Service Layer Error."""


@dataclass
class ServiceExecutionContext:
    task_group: asyncio.TaskGroup
    execution_context: ExecutionContext


class ServicePageInterface(ABC, Generic[K, B, P_co, J_co, R, RD]):
    @abstractmethod
    async def read_page(self, page_id: K) -> B:
        pass

    @abstractmethod
    async def query_database(
        self,
        page_id: K,
        relation: RD,
        datasource_info: DatasourceInfo[K, B, RD],
    ) -> Sequence[B]:
        pass

    # pylint: disable=too-many-positional-arguments, too-many-arguments
    @abstractmethod
    async def build_page_hierarchy(
        self,
        root_page: B,
        level: int = 0,
    ) -> Sequence[B]:
        pass

    @abstractmethod
    async def create_or_update_page(self, page: B) -> bool:
        pass

    @abstractmethod
    async def add_relations_to_page(self, page: B, relations: R) -> None:
        pass

    @abstractmethod
    async def remove_relations_from_page(self, page: B, relations: R) -> None:
        pass

    @abstractmethod
    async def migrate_page(
        self,
        page: B,
        migration_context: MigrationContext[K, P_co, J_co, RD],
        execution_context: ExecutionContext,
    ) -> None:
        pass

    @abstractmethod
    async def migrate_pages(
        self,
        pages: List[B],
        migration_context: MigrationContext[K, P_co, J_co, RD],
        execution_context: ExecutionContext,
    ) -> None:
        pass

    @abstractmethod
    async def verify_page_migration(self, page: B) -> bool:
        pass

    @abstractmethod
    async def migrate_all_pages(self) -> None:
        pass
