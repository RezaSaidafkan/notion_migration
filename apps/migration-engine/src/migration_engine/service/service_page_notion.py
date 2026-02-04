import asyncio
import logging
from asyncio import Task
from dataclasses import dataclass
from typing import List, Union, cast

from common_libs.constants.literal_definitions import (
    DatasourceInfo,
    ExecutionContext,
    JournalJunctionRelations,
    JournalRelations,
    MigrationContext,
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

@dataclass
class ServiceExecutionContext:
    task_group: asyncio.TaskGroup
    execution_context: ExecutionContext


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
        relation: Union[SourceRelations, JournalRelations, JournalJunctionRelations],
        service_execution_context: ServiceExecutionContext
    ) -> Task[List[P]]:
        return service_execution_context.task_group.create_task(
            _timed(
                self.query_database(
                    datasource_info=datasource_info,
                    datasource_type=datasource_type,
                    filter_query={
                        "property": relation.value,
                        "relation": {"contains": str(page.Id.Id)},
                    },
                    execution_context=service_execution_context.execution_context
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
        service_execution_context: ServiceExecutionContext
    ) -> Task[List[P]]:
        return cast(
            Task[List[P]],
            self.get_pages(
                page=cast(P, page),
                datasource_info=datasource_info,
                datasource_type=cast(DB, Page),
                relation=relation,
                service_execution_context=service_execution_context,
            ),
        )

    def get_journal_pages(
        self,
        page: P,
        datasource_info: DatasourceInfo,
        relation: Union[JournalRelations, JournalJunctionRelations],
        service_execution_context: ServiceExecutionContext
    ) -> Task[List[P]]:
        return cast(
            Task[List[P]],
            self.get_pages(
                page=cast(P, page),
                datasource_info=datasource_info,
                datasource_type=cast(DB, JournalPage),
                relation=relation,
                service_execution_context=service_execution_context,
            ),
        )

    async def query_database(
        self,
        datasource_info: DatasourceInfo,
        datasource_type: DB,
        filter_query: dict,
        execution_context: ExecutionContext
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
                    filter_query=filter_query,
                    cursor=cursor,
                    execution_context=execution_context
                )
                pages.extend(cast(List[P], pagination.results))
                cursor = pagination.next_cursor
                exhausted = not pagination.has_more
                if execution_context.DEBUG:
                    if exhausted:
                        logger.debug("Paginated results is exhausted")
                    else:
                        logger.debug("Paginating result to cursor: %s", cursor)
            except RepositoryError as e:
                cursor_msg = f" at cursor: {cursor}" if cursor else ""
                logger.exception(
                    "Failed to query database: %s%s", datasource_info, cursor_msg)
                raise ServiceError(
                    f"Failed to query database: {datasource_info}{cursor_msg}") from e
        return pages

    async def build_page_hierarchy(
        self,
        migration_context: MigrationContext,
        execution_context: ExecutionContext,
        root_page: P,
        level: int = 0,
    ) -> List[P]:  # pylint: disable=too-many-positional-arguments
        """Return pages whose 'Ancestor' relation contains the given parent.

        This method contains the schema knowledge ('Ancestor' relation) and
        delegates to the repository's generic `query_database` method.
        """
        collected: list[P] = []

        if execution_context.DEBUG:
            logger.debug("here")

        try:
            async with asyncio.TaskGroup() as tg:
                service_execution_context = ServiceExecutionContext(
                    task_group=tg,
                    execution_context=execution_context)
                tg.create_task(
                    _timed(
                        self.process_source_recursive(
                            root_page,
                            migration_context,
                            service_execution_context,
                            level,
                            collected,
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
        migration_context: MigrationContext,
        service_execution_context: ServiceExecutionContext,
        level: int,
        collected: list[P]
    ):
        try:
            # create the coroutines and run them concurrently with timing & rate limited
            sub_pages_tasks: Task[List[P]] = self.get_source_pages(
                page=page,
                datasource_info=migration_context.SOURCE_DATASOURCE_INFO,
                relation=SourceRelations.ANCESTORS,
                service_execution_context=service_execution_context,
            )  # type: ignore

            journal_database_tasks: Task[List[P]] = self.get_journal_pages(
                page=page,
                datasource_info=migration_context.JOURNAL_DATASOURCE_INFO,
                relation=migration_context.JOURNAL_JUNCTION_RELATION,
                service_execution_context=service_execution_context,
            )  # type: ignore

            sub_pages, journal_database_pages = await asyncio.gather(
                sub_pages_tasks, journal_database_tasks
            )
            page.Relations = PageRelation(Descendants=None, Ancestors=None, Journals=None)

            if journal_database_pages is not None:
                page.Relations.Journals = journal_database_pages
                for journal_page in journal_database_pages:
                    service_execution_context.task_group.create_task(
                        self.process_journal_recursive(
                            journal_page,
                            migration_context,
                            service_execution_context
                        ),
                    )

            if sub_pages is not None:
                page.Relations.Descendants = sub_pages
                for sub_page in sub_pages:
                    service_execution_context.task_group.create_task(
                        self.process_source_recursive(
                            sub_page,
                            migration_context,
                            service_execution_context,
                            level + 1,
                            collected
                        ),
                    )

            if level == 1 and service_execution_context.execution_context.DEBUG:
                logger.info("The page hierarchy:\n%s", page)
                collected.append(page)
        except (RepositoryError, ServiceError) as e:
            logger.exception("Failed to recurse for page: %s", page)
            raise ServiceError(f"Failed to recurse for page: {page}") from e

    async def process_journal_recursive(
        self,
        page: P,
        migration_context: MigrationContext,
        service_execution_context: ServiceExecutionContext,
    ):
        """Process a journal page recursively, fetching its sub-journal pages.

        Assigns the found sub-journal pages to the Relations.Descendants / Relations.Ancestors
        attributes of the page.
        """
        sub_journal_pages: List[P] = await self.get_journal_pages(
            page=page,
            datasource_info=migration_context.JOURNAL_DATASOURCE_INFO,
            relation=JournalRelations.ANCESTORS,
            service_execution_context=service_execution_context,
        )

        if sub_journal_pages:
            page.Relations = JournalRelation(
                Descendants=cast(List[P], sub_journal_pages),
                Ancestors=cast(List[P], [page]),
            )
            for journ_page in sub_journal_pages:
                service_execution_context.task_group.create_task(
                    self.process_journal_recursive(
                        journ_page,
                        migration_context,
                        service_execution_context,
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
        migration_context: MigrationContext,
        execution_context: ExecutionContext
    ) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def migrate_pages(
        self,
        pages: List[P],
        migration_context: MigrationContext,
        execution_context: ExecutionContext
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
