from abc import ABC, abstractmethod
from typing import Generic
from uuid import UUID

from common_libs.models.client_models import RD, B, K, PaginationResult
from common_libs.models.context import ExecutionContext


class RepositoryError(Exception):
    """Base Repository Layer Error."""


class RepositoryInterface(Generic[K, B, RD], ABC):
    @abstractmethod
    async def read_page(self, page_id: K, debug: bool = False) -> B:
        pass

    # pylint: disable=too-many-positional-arguments, too-many-arguments
    @abstractmethod
    async def query_database(
        self,
        page_id: K,
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
