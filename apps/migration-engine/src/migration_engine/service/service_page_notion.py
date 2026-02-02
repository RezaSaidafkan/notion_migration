import asyncio
import logging
from asyncio import Task
from dataclasses import dataclass
from typing import List, Union, cast

from common_libs.constants.literal_definitions import (
    DatasourceInfo,
    JournalRelations,
    SourceRelations,
)
from common_libs.models.client_models import (
    DB,
    JournalPage,
    JournalRelation,
    K,
    P,
    Page,
    PageRelation,
    R,
)

from migration_engine.config.load_config import GLOBAL_CONFIG
from migration_engine.repo.repo_page_interface import RepositoryError
from migration_engine.repo.repo_page_notion import (
    NotionRepoJournalPage,
    NotionRepoPage,
    NotionRepository,
)
from migration_engine.service.service_page_interface import (
    ServiceError,
    ServicePageInterface,
)
from migration_engine.utils.timer import _timed

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessingContext:
    source_database_info: DatasourceInfo
    journal_database_info: DatasourceInfo
    journal_relation: JournalRelations


class ServicePage(ServicePageInterface[K, P, DB, R]):
    """Service layer for page-related domain logic.

    Keep schema- and business-logic here. The repository should expose
    generic persistence queries (like `query_database`) without hardcoding
    domain property names.
    """

    def __init__(
        self, repo_source: NotionRepoPage, repo_journal: NotionRepoJournalPage
    ) -> None:
        self._repo_source = repo_source
        self._repo_journal = repo_journal

    async def read_page(self, page_id: K) -> P:
        try:
            retrieved_page = await self._repo_source.read_page(page_id)
            return cast(
                P,
                Page(
                    Id=page_id,
                    Icon=retrieved_page.Icon,
                    Properties=retrieved_page.Properties,
                ),
            )
        except RepositoryError as e:
            logging.exception("Failed to read page_id: %s", page_id)
            raise ServiceError(f"Failed to read page_id: {page_id}") from e

    # pylint: disable=too-many-positional-arguments, too-many-arguments
    def get_pages(
        self,
        page: P,
        datasource_info: DatasourceInfo,
        datasource_type: DB,
        relation: Union[SourceRelations, JournalRelations],
        tg: asyncio.TaskGroup,
    ) -> Task[List[P]]:
        return tg.create_task(
            _timed(
                self.query_database(
                    datasource_info=datasource_info,
                    datasource_type=datasource_type,
                    filter_query={
                        "property": relation.value,
                        "relation": {"contains": str(page.Id.Id)},
                    },
                ),
                page,
                "query_database:sub_pages",
            ),
        )

    def get_source_pages(
        self,
        page: P,
        datasource_info: DatasourceInfo,
        relation: SourceRelations,
        tg: asyncio.TaskGroup,
    ) -> Task[List[P]]:
        return cast(
            Task[List[P]],
            self.get_pages(
                page=cast(P, page),
                datasource_info=datasource_info,
                datasource_type=cast(DB, Page),
                relation=relation,
                tg=tg,
            ),
        )

    def get_journal_pages(
        self,
        page: P,
        datasource_info: DatasourceInfo,
        relation: JournalRelations,
        tg: asyncio.TaskGroup,
    ) -> Task[List[P]]:
        return cast(
            Task[List[P]],
            self.get_pages(
                page=cast(P, page),
                datasource_info=datasource_info,
                datasource_type=cast(DB, JournalPage),
                relation=relation,
                tg=tg,
            ),
        )

    async def query_database(
        self, datasource_info: DatasourceInfo, datasource_type: DB, filter_query: dict
    ) -> List[P]:
        repo: NotionRepository
        if datasource_type is Page:
            repo = self._repo_source
        elif datasource_type is JournalPage:
            repo = self._repo_journal
        else:
            # This branch is unreachable due to the overloads, but good for runtime safety
            raise ServiceError(f"Unsupported database_type: {datasource_type}")

        exhausted = False
        cursor = None
        pages: List[P] = []

        while not exhausted:
            try:
                pagination = await repo.query_database(
                    data_source_id=datasource_info.DatasourceId,
                    page_size=GLOBAL_CONFIG.pagination_size,
                    filter_query=filter_query,
                    cursor=cursor,
                )
                pages.extend(cast(List[P], pagination.results))
                cursor = pagination.next_cursor
                exhausted = not pagination.has_more
            except RepositoryError as e:
                cursor_msg = f" at cursor: {cursor}" if cursor else ""
                logger.exception(
                    "Failed to query database: %s%s", datasource_info, cursor_msg)
                raise ServiceError(
                    f"Failed to query database: {datasource_info}{cursor_msg}") from e
        return pages

    async def build_page_hierarchy(
        self,
        root_page: P,
        source_datasource_info: DatasourceInfo,
        journal_datasource_info: DatasourceInfo,
        journal_relation: JournalRelations,
        level: int = 0,
    ) -> List[P]:  # pylint: disable=too-many-positional-arguments
        """Return pages whose 'Ancestor' relation contains the given parent.

        This method contains the schema knowledge ('Ancestor' relation) and
        delegates to the repository's generic `query_database` method.
        """
        collected: list[P] = []
        context = ProcessingContext(
            source_database_info=source_datasource_info,
            journal_database_info=journal_datasource_info,
            journal_relation=journal_relation,
        )

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(
                    _timed(
                        self.process_source_recursive(
                            root_page,
                            context,
                            level,
                            collected,
                            tg,
                        ),
                        root_page,
                        "root_page",
                    )
                )
        except* ServiceError as eg:
            raise ServiceError(
                f"Failed to recursively build page hierarchy for: {root_page}") from eg
        except* Exception as e:
            raise ServiceError("An unknown Exception was raised") from e

        return collected

    async def process_source_recursive(
        self,
        page: P,
        context: ProcessingContext,
        level: int,
        collected: list[P],
        tg: asyncio.TaskGroup,
    ):
        try:
            # create the coroutines and run them concurrently with timing & rate limited
            sub_pages_tasks: Task[List[P]] = self.get_source_pages(
                page=page,
                datasource_info=context.source_database_info,
                relation=SourceRelations.ANCESTORS,
                tg=tg,
            )  # type: ignore

            journal_database_tasks: Task[List[P]] = self.get_journal_pages(
                page=page,
                datasource_info=context.journal_database_info,
                relation=context.journal_relation,
                tg=tg,
            )  # type: ignore

            sub_pages, journal_database_pages = await asyncio.gather(
                sub_pages_tasks, journal_database_tasks
            )
            page.Relations = PageRelation(Descendants=None, Ancestors=None, Journals=None)

            if journal_database_pages is not None:
                page.Relations.Journals = journal_database_pages
                for journ_page in journal_database_pages:
                    tg.create_task(
                        self.process_journal_recursive(
                            journ_page,
                            context.journal_database_info,
                            context.journal_relation,
                            tg,
                        ),
                    )

            if sub_pages is not None:
                page.Relations.Descendants = sub_pages
                for sub_page in sub_pages:
                    tg.create_task(
                        self.process_source_recursive(
                            sub_page,
                            context,
                            level + 1,
                            collected,
                            tg,
                        ),
                    )

            if level == 1 and GLOBAL_CONFIG.debug:
                logger.info("The page hierarchy:\n%s", page)
                collected.append(page)
        except (RepositoryError, ServiceError) as e:
            logger.exception("Failed to recurse for page: %s", page)
            raise ServiceError(f"Failed to recurse for page: {page}") from e

    async def process_journal_recursive(
        self,
        page: P,
        journal_database_info: DatasourceInfo,
        journal_relation: JournalRelations,
        tg: asyncio.TaskGroup,
    ):
        """Process a journal page recursively, fetching its sub-journal pages.

        Assigns the found sub-journal pages to the Relations.Descendants / Relations.Ancestors
        attributes of the page.
        """
        sub_journal_pages: List[P] = await self.get_journal_pages(
            page=page,
            datasource_info=journal_database_info,
            relation=JournalRelations.ANCESTORS,
            tg=tg,
        )

        if sub_journal_pages:
            page.Relations = JournalRelation(
                Descendants=cast(List[P], sub_journal_pages),
                Ancestors=cast(List[P], [page]),
            )
            for journ_page in sub_journal_pages:
                tg.create_task(
                    self.process_journal_recursive(
                        journ_page,
                        journal_database_info,
                        journal_relation,
                        tg,
                    ),
                )

    async def create_or_update_page(self, page: P) -> bool:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def add_relations_to_page(self, page: P, relations: R) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def remove_relations_from_page(self, page: P, relations: R) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def migrate_page(
        self,
        page: P,
        source_datasource_info: DatasourceInfo,
        target_datasource_info: DatasourceInfo,
    ) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def migrate_pages(
        self,
        pages: List[P],
        source_datasource_info: DatasourceInfo,
        target_datasource_info: DatasourceInfo,
    ) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def verify_page_migration(self, page: P) -> bool:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def migrate_all_pages(self) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )
