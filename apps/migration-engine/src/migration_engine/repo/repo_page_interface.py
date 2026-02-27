from abc import ABC, abstractmethod
from typing import Generic
from uuid import UUID

from common_libs.models.client_models import RD, BP, B, PaginationResult
from common_libs.models.context import ExecutionContext


class RepositoryError(Exception):
    """Base Repository Layer Error."""


class RepositoryInterface(Generic[BP, B, RD], ABC):
    @abstractmethod
    async def read_page(self, page: BP, debug: bool = False) -> B:
        pass

    # pylint: disable=too-many-positional-arguments, too-many-arguments
    @abstractmethod
    async def query_database(
        self,
        page: BP,
        execution_context: ExecutionContext,
        data_source_id: UUID,
        relation: RD,
        cursor: str | None = None
    ) -> PaginationResult[B]:
        pass

    @abstractmethod
    async def create_page(self, page: B, debug: bool) -> bool:
        pass

    @abstractmethod
    async def update_page(self, page: B, debug: bool) -> bool:
        pass
