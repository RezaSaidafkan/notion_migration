import asyncio
import logging
from asyncio import Task
from typing import List, Sequence

from common_libs.constants.literal_definitions import (
    ExecutionContext,
    JournalRelationsDefinition,
    RelationDefinitions,
    TaskRelationsDefinition,
)
from common_libs.models.client_models import (
    B,
    CommonPage,
    DatasourceInfo,
    JournalPage,
    JournalRelation,
    MigrationContext,
    P_co,
    PageId,
    RelativePages,
    TaskPage,
    TaskRelation,
)

from migration_engine.repo.repo_page_interface import (
    RepositoryError,
)
from migration_engine.service.service_page_interface import (
    ServiceError,
    ServiceExecutionContext,
    ServicePageInterface,
)
from migration_engine.utils.timer import timed

logger = logging.getLogger(__name__)



class ServicePage(
    ServicePageInterface[PageId,
                         TaskPage,
                         TaskPage,
                         JournalPage,
                         RelativePages,
                         RelationDefinitions]):
    """Service layer for page-related domain logic.

    Keep schema- and business-logic here. The repository should expose
    generic persistence queries (like `query_database`) without hardcoding
    domain property names.
    """

    def __init__(self,
                 execution_context: ExecutionContext,
                 migration_context: MigrationContext[
                     PageId,
                     TaskPage,
                     JournalPage,
                     RelationDefinitions]) -> None:
        self._execution_context = execution_context
        self._migration_context = migration_context
        self._service_execution_context: ServiceExecutionContext

    async def read_page(self, page_id: PageId) -> TaskPage:
        try:
            retrieved_page = await self._migration_context.\
                SOURCE_DATASOURCE_INFO.Repo.read_page(page_id)
            return TaskPage(
                    Id=page_id,
                    Icon=retrieved_page.Icon,
                    Properties=retrieved_page.Properties,
                )
        except RepositoryError as e:
            logging.exception("Failed to read page_id: %s", page_id)
            raise ServiceError(f"Failed to read page_id: {page_id}") from e

    async def query_database(
        self,
        page_id: PageId,
        relation: RelationDefinitions,
        datasource_info: DatasourceInfo[PageId, B, RelationDefinitions],
    ) -> Sequence[B]:
        exhausted = False
        cursor = None
        pages: List[B] = []

        while not exhausted:
            try:
                pagination = await datasource_info.Repo.query_database(
                    page_id=page_id,
                    relation=relation,
                    data_source_id=datasource_info.DatasourceId,
                    cursor=cursor,
                    execution_context=self._execution_context
                )
                pages.extend(pagination.results)
                cursor = pagination.next_cursor
                exhausted = not pagination.has_more
                if self._execution_context.DEBUG:
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
        root_page: TaskPage,
        level: int = 0,
    ) -> Sequence[TaskPage]:  # pylint: disable=too-many-positional-arguments
        """Return pages whose 'Ancestor' relation contains the given parent.

        This method contains the schema knowledge ('Ancestor' relation) and
        delegates to the repository's generic `query_database` method.
        """
        collected: List[TaskPage] = []

        if self._execution_context.DEBUG:
            logger.debug("here")

        try:
            async with asyncio.TaskGroup() as tg:
                self._service_execution_context = ServiceExecutionContext(
                    task_group=tg,
                    execution_context=self._execution_context)

                tg.create_task(
                    timed(
                        self.process_source_recursive(
                            root_page,
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

    # pylint: disable=too-many-positional-arguments, too-many-arguments
    def create_task_sub_pages(
        self,
        page: CommonPage,
        datasource_info: DatasourceInfo[PageId, B, RelationDefinitions],
        relation: RelationDefinitions
    ) -> Task[Sequence[B]]:
        return self._service_execution_context.task_group.create_task(
            timed(
                self.query_database(
                    page_id=page.Id,
                    relation=relation,
                    datasource_info=datasource_info
                ),
                page,
                "query_database:sub_pages",
            ),
        )

    async def process_source_recursive(
        self,
        page: TaskPage,
        level: int,
        collected: List[TaskPage]
    ):
        try:
            # create the coroutines and run them concurrently with timing & rate limited
            task_subpages_tasks: Task[Sequence[TaskPage]] = self.create_task_sub_pages(
                page=page,
                datasource_info=self._migration_context.SOURCE_DATASOURCE_INFO,
                relation=TaskRelationsDefinition.ANCESTORS
            )

            journal_pages_tasks: Task[Sequence[JournalPage]] = self.create_task_sub_pages(
                page=page,
                datasource_info=self._migration_context.JOURNAL_DATASOURCE_INFO,
                relation=self._migration_context.JUNCTION_RELATION_DEFINITION,
            )

            task_subpages, journal_pages = await asyncio.gather(
                task_subpages_tasks, journal_pages_tasks
            )

            page.Relations = TaskRelation(Descendants=None, Ancestors=None, Journals=None)

            if journal_pages != []:
                page.Relations.Journals = journal_pages
                for journal_page in journal_pages:
                    self._service_execution_context.task_group.create_task(
                        self.process_journal_recursive(
                            journal_page,
                        ),
                    )

            if task_subpages != []:
                page.Relations.Descendants = task_subpages
                for sub_page in task_subpages:
                    self._service_execution_context.task_group.create_task(
                        self.process_source_recursive(
                            sub_page,
                            level + 1,
                            collected
                        ),
                    )

            if level == 1 and self._service_execution_context.execution_context.DEBUG:
                logger.info("The page hierarchy:\n%s", page)
                collected.append(page)
        except (RepositoryError, ServiceError) as e:
            logger.exception("Failed to recurse for page: %s", page.Properties.Title)
            raise ServiceError(f"Failed to recurse for page: {page.Properties.Title}") from e

    async def process_journal_recursive(self, page: JournalPage):
        """Process a journal page recursively, fetching its sub-journal pages.

        Assigns the found sub-journal pages to the Relations.Descendants / Relations.Ancestors
        attributes of the page.
        """
        sub_journal_pages: Sequence[JournalPage] = await self.create_task_sub_pages(
            page=page,
            datasource_info=self._migration_context.JOURNAL_DATASOURCE_INFO,
            relation=JournalRelationsDefinition.ANCESTOR,
        )

        if sub_journal_pages:
            page.Relations = JournalRelation(
                JunctionRelation=self._migration_context.JUNCTION_RELATION_DEFINITION,
                Descendants=sub_journal_pages,
                Ancestors=[page],
            )
            for journ_page in sub_journal_pages:
                self._service_execution_context.task_group.create_task(
                    self.process_journal_recursive(journ_page),
                )

    async def create_or_update_page(self, page: TaskPage) -> bool:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def add_relations_to_page(self, page: TaskPage, relations: RelativePages) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def remove_relations_from_page(self, page: TaskPage, relations: RelativePages) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def migrate_page(
        self,
        page: TaskPage,
        migration_context: MigrationContext[PageId, TaskPage, JournalPage, RelationDefinitions],
        execution_context: ExecutionContext
    ) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def migrate_pages(
        self,
        pages: List[P_co],
        migration_context: MigrationContext[PageId, TaskPage, JournalPage, RelationDefinitions],
        execution_context: ExecutionContext
    ) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def verify_page_migration(self, page: CommonPage) -> bool:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def migrate_all_pages(self) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )
