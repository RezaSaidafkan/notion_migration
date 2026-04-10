from abc import ABC, abstractmethod
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any, Generic, List, Sequence

from common_libs.models.client_models import BP, RD, B, J_co, P_co, R
from common_libs.models.context import (
    DatasourceInfo,
    ExecutionContext,
    MigrationContext,
)


class ServiceError(Exception):
    """Base Service Layer Error."""


@dataclass
class ServiceExecutionContext:
    # task_group: asyncio.TaskGroup
    execution_context: ExecutionContext


class ServicePageInterface(ABC, Generic[BP, B, P_co, J_co, R, RD]):
    @abstractmethod
    def read_page(
        self,
        page: BP,
        execution_context: ExecutionContext,
        migration_context: MigrationContext[BP, P_co, J_co, RD]
        ) -> Coroutine[Any, Any, B]:
        pass

    @abstractmethod
    def query_database(
        self,
        page: BP,
        relation: RD,
        datasource_info: DatasourceInfo[BP, B, RD],
        execution_context: ExecutionContext
        ) -> Coroutine[Any, Any, Sequence[B]]:
        pass

    # pylint: disable=too-many-positional-arguments, too-many-arguments
    @abstractmethod
    def build_page_hierarchy(
        self,
        page: B,
        migration_context: MigrationContext[BP, P_co, J_co, RD],
        execution_context: ExecutionContext,
        level: int = 0
        ) -> Coroutine[Any, Any, Sequence[B]]:
        pass

    @abstractmethod
    def create_or_update_page(
        self,
        page: B,
        migration_context: MigrationContext[BP, P_co, J_co, RD],
        execution_context: ExecutionContext
        ) -> Coroutine[Any, Any, bool]:
        pass

    @abstractmethod
    def add_relations_to_page(
        self,
        page: B,
        relations: R,
        migration_context: MigrationContext[BP, P_co, J_co, RD],
        execution_context: ExecutionContext
        ) -> Coroutine[Any, Any, None]:
        pass

    @abstractmethod
    def remove_relations_from_page(
        self,
        page: B,
        relations: R,
        migration_context: MigrationContext[BP, P_co, J_co, RD],
        execution_context: ExecutionContext
        ) -> Coroutine[Any, Any, None]:
        pass

    @abstractmethod
    def migrate_page(
        self,
        page: B,
        migration_context: MigrationContext[BP, P_co, J_co, RD],
        execution_context: ExecutionContext
        ) -> Coroutine[Any, Any, None]:
        pass

    @abstractmethod
    def migrate_pages(
        self,
        pages: List[B],
        migration_context: MigrationContext[BP, P_co, J_co, RD],
        execution_context: ExecutionContext
        ) -> Coroutine[Any, Any, None]:
        pass

    @abstractmethod
    def verify_page_migration(
        self,
        page: B,
        migration_context: MigrationContext[BP, P_co, J_co, RD],
        execution_context: ExecutionContext
        ) -> Coroutine[Any, Any, bool]:
        pass

    @abstractmethod
    def migrate_all_pages(
        self,
        migration_context: MigrationContext[BP, P_co, J_co, RD],
        execution_context: ExecutionContext
        ) -> Coroutine[Any, Any, None]:
        pass
