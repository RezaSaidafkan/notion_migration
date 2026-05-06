from abc import ABC, abstractmethod
from collections.abc import Coroutine
from typing import Any, Dict, Generic, List, Optional
from uuid import UUID

from common_libs.models.client_models import BP, RD, C, PaginationResult
from common_libs.models.context import ExecutionContext

QueryType = Dict[str, str | int | Dict[str, str | Dict[str, str]]]


class RepositoryError(Exception):
    """Base Repository Layer Error."""

    # pylint: disable=too-many-positional-arguments, too-many-arguments
    def __init__(
                self,
                query: Optional[QueryType] = None,
                message: Optional[str] = None,
                code: Optional[str] = None,
                status: Optional[int] = None,
                error_type: Optional[Any] = None
    ) -> None:
        super().__init__()
        self.message = message
        self.code = code
        self.status = status
        self.error_type = error_type
        self.query = query

    def __str__(self) -> str:
        parts: List[str] = []
        if self.status:
            parts.append(f"[{self.status}]")
        if self.code:
            parts.append(f"({self.code})")

        # Use a default message if none is provided
        msg = self.message or "An unexpected repository error occurred."
        parts.append(msg)

        return " ".join(parts)

class RepositoryInterface(Generic[BP, C, RD], ABC):
    @abstractmethod
    def read_page(self, page: BP, debug: bool = False
    ) -> Coroutine[Any, Any, C]:
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
    ) -> Coroutine[Any, Any, PaginationResult[C]]:
        pass

    @abstractmethod
    def create_page(
        self,
        page: C,
        execution_context: ExecutionContext,
        parent_page_id: UUID,
        debug: bool
    ) -> Coroutine[Any, Any, bool]:
        pass

    @abstractmethod
    def update_page(self, page: C, debug: bool
    ) -> Coroutine[Any, Any, bool]:
        pass
