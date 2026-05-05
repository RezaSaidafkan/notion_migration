from abc import ABC, abstractmethod
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any, Generic, List, Sequence, Union

from common_libs.models.client_models import BP, RD, C, J_co, P_co, R
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


class ServicePageInterface(ABC, Generic[BP, C, P_co, J_co, R, RD]):
    @abstractmethod
    def read_page(
        self,
        page: BP,
        execution_context: ExecutionContext,
        migration_context: MigrationContext[BP, P_co, J_co, RD]
        ) -> Coroutine[Any, Any, C]:
        pass

    @abstractmethod
    def query_database(
        self,
        page: BP,
        relation: RD,
        datasource_info: DatasourceInfo[BP, C, RD],
        execution_context: ExecutionContext
        ) -> Coroutine[Any, Any, Sequence[C]]:
        pass

    # pylint: disable=too-many-positional-arguments, too-many-arguments
    @abstractmethod
    def build_page_hierarchy(
        self,
        page: C,
        migration_context: MigrationContext[BP, P_co, J_co, RD],
        execution_context: ExecutionContext,
        level: int = 0
        ) -> Coroutine[Any, Any, None]:
        pass

    @abstractmethod
    def get_task_sub_pages(
        self,
        page: C,
        datasource_info: DatasourceInfo[BP, Any, RD],
        relation: RD,
        execution_context: ExecutionContext
    ) -> Coroutine[Any, Any, Sequence[Union[P_co, J_co]]]:
        pass


    @abstractmethod
    def create_or_update_page(
        self,
        page: C,
        migration_context: MigrationContext[BP, P_co, J_co, RD],
        execution_context: ExecutionContext
        ) -> Coroutine[Any, Any, bool]:
        pass

    @abstractmethod
    def add_relations_to_page(
        self,
        page: C,
        relations: R,
        migration_context: MigrationContext[BP, P_co, J_co, RD],
        execution_context: ExecutionContext
        ) -> Coroutine[Any, Any, None]:
        pass

    @abstractmethod
    def remove_relations_from_page(
        self,
        page: C,
        relations: R,
        migration_context: MigrationContext[BP, P_co, J_co, RD],
        execution_context: ExecutionContext
        ) -> Coroutine[Any, Any, None]:
        pass

    @abstractmethod
    def migrate_page(
        self,
        page: C,
        migration_context: MigrationContext[BP, P_co, J_co, RD],
        execution_context: ExecutionContext
        ) -> Coroutine[Any, Any, None]:
        pass

    @abstractmethod
    def migrate_pages(
        self,
        pages: List[C],
        migration_context: MigrationContext[BP, P_co, J_co, RD],
        execution_context: ExecutionContext
        ) -> Coroutine[Any, Any, None]:
        pass

    @abstractmethod
    def verify_page_migration(
        self,
        page: C,
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
