from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, TypeVar

T = TypeVar("T")  # CommonPage
K = TypeVar("K")  # page id
R = TypeVar("R")  # Pagination result


class RepositoryError(Exception):
    """Base Repository Layer Error."""


class RepositoryInterface(Generic[K, T, R], ABC):
    @abstractmethod
    async def read_page(self, page_id: K, debug: bool = False) -> T:
        pass

    # pylint: disable=too-many-positional-arguments, too-many-arguments
    @abstractmethod
    async def query_database(
        self,
        data_source_id: str,
        page_size: int,
        filter_query: Dict[str, Any],
        cursor: str | None,
        debug: bool,
    ) -> R:
        pass

    @abstractmethod
    async def create_page(self, page: T, debug: bool) -> bool:
        pass

    @abstractmethod
    async def update_page(self, page: T, debug: bool) -> bool:
        pass
