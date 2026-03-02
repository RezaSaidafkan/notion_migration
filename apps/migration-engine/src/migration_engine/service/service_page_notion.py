import asyncio
import logging
from asyncio import Task
from collections.abc import Coroutine
from typing import Any, List, Sequence

from common_libs.constants.literal_definitions import (
    JournalRelationsDefinition,
    RelationDefinitions,
    TaskRelationsDefinition,
)
from common_libs.models.client_models import (
    B,
    BasePage,
    CommonPage,
    JournalPage,
    JournalRelation,
    P_co,
    RelativePages,
    TaskPage,
    TaskRelation,
)
from common_libs.models.context import (
    DatasourceInfo,
    ExecutionContext,
    MigrationContext,
)
from common_libs.utils.tracing import tracer

from migration_engine.repo.repo_page_interface import (
    RepositoryError,
)
from migration_engine.service.service_page_interface import (
    ServiceError,
    ServiceExecutionContext,
    ServicePageInterface,
)

logger = logging.getLogger(__name__)



class ServicePage(
    ServicePageInterface[BasePage,
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

    def __init__(self) -> None:
        self._service_execution_context: ServiceExecutionContext

    # pylint: disable=invalid-overridden-method
    @tracer
    async def read_page(
        self,
        page: BasePage,
        execution_context: ExecutionContext,
        migration_context: MigrationContext[
            BasePage,
            TaskPage,
            JournalPage,
            RelationDefinitions]) -> TaskPage:
        try:
            retrieved_page = await migration_context.\
                source_datasource_info.repo.read_page(page)
            return TaskPage(
                    Id=page.Id,
                    Icon=retrieved_page.Icon,
                    Properties=retrieved_page.Properties,
                )
        # pylint: disable=raise-missing-from
        except RepositoryError:
            logging.exception(
                "Failed to read page_id: %s", page)
            raise ServiceError(
                f"Failed to read page_id: {page}")

    # pylint: disable=invalid-overridden-method
    @tracer
    async def query_database(
        self,
        page: BasePage,
        relation: RelationDefinitions,
        datasource_info: DatasourceInfo[BasePage, B, RelationDefinitions],
        execution_context: ExecutionContext,
        ) -> Sequence[B]:
        exhausted = False
        cursor = None
        pages: List[B] = []

        while not exhausted:
            try:
                pagination = await datasource_info.repo.query_database(
                    page=page,
                    execution_context=execution_context,
                    data_source_id=datasource_info.datasource_id,
                    relation=relation,
                    cursor=cursor
                )
                pages.extend(pagination.results)
                cursor = pagination.next_cursor
                exhausted = not pagination.has_more
                if execution_context.debug:
                    if exhausted:
                        logger.debug("Paginated results is exhausted")
                    else:
                        logger.debug("Paginating result to cursor: %s", cursor)
            # pylint: disable=raise-missing-from
            except RepositoryError:
                cursor_msg = f" at cursor: {cursor}" if cursor else ""
                logger.exception(
                    "Failed to query database:\t%s,\tcursor:\t%s,\tpage:\t%s",
                    datasource_info, cursor_msg, page.Id)
                raise ServiceError(
                    f"Failed to query database:\t\
                    {datasource_info},\t\
                    cursor:\t{cursor_msg},\t\
                    page:\t{page.Id}",
                    )
        return pages

    # pylint: disable=invalid-overridden-method
    @tracer
    async def build_page_hierarchy(
        self,
        page: TaskPage,
        migration_context: MigrationContext[
            BasePage,
            TaskPage,
            JournalPage,
            RelationDefinitions],
        execution_context: ExecutionContext,
        level: int = 0,
    ) -> Sequence[TaskPage]:  # pylint: disable=too-many-positional-arguments
        """Return pages whose 'Ancestor' relation contains the given parent.

        This method contains the schema knowledge ('Ancestor' relation) and
        delegates to the repository's generic `query_database` method.
        """
        collected: List[TaskPage] = []

        try:
            async with asyncio.TaskGroup() as tg:
                self._service_execution_context = ServiceExecutionContext(
                    task_group=tg,
                    execution_context=execution_context)

                tg.create_task(
                        self.process_source_recursive(
                            page,
                            level,
                            collected,
                            migration_context,
                            execution_context
                        )
                    )
        # pylint: disable=raise-missing-from
        except* Exception as eg:
            for e in eg.exceptions:
                logger.exception(e)
            logger.exception(
                "An unknown Exception was raised for: %s", page.Properties.Title)
            raise ServiceError(
                f"An unknown Exception was raised for: {page.Properties.Title}")

        return collected

    # pylint: disable=invalid-overridden-method
    # pylint: disable=too-many-positional-arguments, too-many-arguments
    def create_task_sub_pages(
        self,
        page: CommonPage,
        datasource_info: DatasourceInfo[BasePage, B, RelationDefinitions],
        relation: RelationDefinitions,
        execution_context: ExecutionContext,
    ) -> Coroutine[Any, Any, Sequence[B]]:
        """Create a task to query sub-pages asynchronously.
        Note: Exceptions raised by the task will be collected by the TaskGroup
        and re-raised as ExceptionGroup when the TaskGroup exits.
        """
        try:
            return self.query_database(
                page=BasePage(Id=page.Id),
                execution_context=execution_context,
                relation=relation,
                datasource_info=datasource_info
            )
        except ServiceError as se:
            logger.exception(
                "Failed to create sub page for %s", page
            )
            raise ServiceError(
                f"Failed to create sub page for {page}",
            ) from se

    async def process_source_recursive(
        self,
        page: TaskPage,
        level: int,
        collected: List[TaskPage],
        migration_context: MigrationContext[
            BasePage,
            TaskPage,
            JournalPage,
            RelationDefinitions],
        execution_context: ExecutionContext,
    ):
        try:
            # create the coroutines and run them concurrently with timing & rate limited
            task_subpages_tasks: Task[Sequence[TaskPage]] = (
                self._service_execution_context.task_group
                .create_task(
                    self.create_task_sub_pages(
                        page=page,
                        datasource_info=migration_context.source_datasource_info,
                        relation=TaskRelationsDefinition.ANCESTORS,
                        execution_context=execution_context
                        )
                    )
            )

            journal_pages_tasks: Task[Sequence[JournalPage]] = (
                self._service_execution_context.task_group\
                .create_task(
                    self.create_task_sub_pages(
                        page=page,
                        datasource_info=migration_context.journal_datasource_info,
                        relation=migration_context.junction_relation_definition,
                        execution_context=execution_context
                        )
                    )
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
                            migration_context,
                            execution_context
                        ),
                    )

            if task_subpages != []:
                page.Relations.Descendants = task_subpages
                for sub_page in task_subpages:
                    self._service_execution_context.task_group.create_task(
                        self.process_source_recursive(
                            sub_page,
                            level + 1,
                            collected,
                            migration_context,
                            execution_context
                        ),
                    )

            if level == 1 and self._service_execution_context.execution_context.debug:
                logger.info("The page hierarchy:\n%s", page)
                collected.append(page)
        except (RepositoryError, ServiceError) as e:
            logger.exception(
                "Failed to recurse for page: %s", page.Properties.Title)
            raise ServiceError(
                f"Failed to recurse for page: {page.Properties.Title}") from e

    async def process_journal_recursive(
        self,
        page: JournalPage,
        migration_context: MigrationContext[
            BasePage,
            TaskPage,
            JournalPage,
            RelationDefinitions],
        execution_context: ExecutionContext):
        """Process a journal page recursively, fetching its sub-journal pages.

        Assigns the found sub-journal pages to the Relations.Descendants / Relations.Ancestors
        attributes of the page.
        """
        sub_journal_pages: Sequence[JournalPage] = await self.create_task_sub_pages(
            page=page,
            datasource_info=migration_context.journal_datasource_info,
            relation=JournalRelationsDefinition.ANCESTOR,
            execution_context=execution_context
        )

        if sub_journal_pages:
            page.Relations = JournalRelation(
                JunctionRelation=migration_context.junction_relation_definition,
                Descendants=sub_journal_pages,
                Ancestors=[page],
            )
            for journ_page in sub_journal_pages:
                self._service_execution_context.task_group.create_task(
                self.process_journal_recursive(
                    journ_page,
                    migration_context,
                    execution_context),
                )

    async def create_or_update_page(
        self,
        page: TaskPage,
        migration_context: MigrationContext[
            BasePage,
            TaskPage,
            JournalPage,
            RelationDefinitions],
        execution_context: ExecutionContext) -> bool:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def add_relations_to_page(
        self,
        page: TaskPage,
        relations: RelativePages,
        migration_context: MigrationContext[
            BasePage,
            TaskPage,
            JournalPage,
            RelationDefinitions],
        execution_context: ExecutionContext) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def remove_relations_from_page(
        self,
        page: TaskPage,
        relations: RelativePages,
        migration_context: MigrationContext[
            BasePage,
            TaskPage,
            JournalPage,
            RelationDefinitions],
        execution_context: ExecutionContext) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def migrate_page(
        self,
        page: TaskPage,
        migration_context: MigrationContext[BasePage, TaskPage, JournalPage, RelationDefinitions],
        execution_context: ExecutionContext
    ) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def migrate_pages(
        self,
        pages: List[P_co],
        migration_context: MigrationContext[BasePage, TaskPage, JournalPage, RelationDefinitions],
        execution_context: ExecutionContext
    ) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def verify_page_migration(
        self,
        page: CommonPage,
        migration_context: MigrationContext[BasePage, TaskPage, JournalPage, RelationDefinitions],
        execution_context: ExecutionContext) -> bool:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def migrate_all_pages(
        self,
        migration_context: MigrationContext[BasePage, TaskPage, JournalPage, RelationDefinitions],
        execution_context: ExecutionContext) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )
