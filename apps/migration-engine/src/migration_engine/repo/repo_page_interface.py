from abc import ABC, abstractmethod
from collections.abc import Coroutine
from typing import Any, Generic
from uuid import UUID

from common_libs.models.client_models import BP, RD, B, PaginationResult
from common_libs.models.context import ExecutionContext


class RepositoryError(Exception):
    """Base Repository Layer Error."""


class RepositoryInterface(Generic[BP, B, RD], ABC):
    @abstractmethod
    def read_page(self, page: BP, debug: bool = False
    ) -> Coroutine[Any, Any, B]:
        pass

    # pylint: disable=too-many-positional-arguments, too-many-arguments
    @abstractmethod
    def query_database(
        self,
        page: BP,
        execution_context: ExecutionContext,
        data_source_id: UUID,
        relation: RD,
        cursor: str | None = None
    ) -> Coroutine[Any, Any, PaginationResult[B]]:
        pass

    @abstractmethod
    def create_page(self, page: B, debug: bool
    ) -> Coroutine[Any, Any, bool]:
        pass

    @abstractmethod
    def update_page(self, page: B, debug: bool
    ) -> Coroutine[Any, Any, bool]:
        pass
