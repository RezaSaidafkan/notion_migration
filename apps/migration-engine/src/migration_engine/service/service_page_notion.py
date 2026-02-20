import asyncio
import logging
from asyncio import Task
from typing import List, Sequence

from common_libs.constants.literal_definitions import (
    JournalRelationsDefinition,
    RelationDefinitions,
    TaskRelationsDefinition,
)
from common_libs.models.client_models import (
    B,
    CommonPage,
    JournalPage,
    JournalRelation,
    P_co,
    PageId,
    RelativePages,
    TaskPage,
    TaskRelation,
)
from common_libs.models.context import (
    DatasourceInfo,
    ExecutionContext,
    MigrationContext,
)

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

    def __init__(self) -> None:
        self._service_execution_context: ServiceExecutionContext

    async def read_page(
        self,
        page_id: PageId,
        execution_context: ExecutionContext,
        migration_context: MigrationContext[
            PageId,
            TaskPage,
            JournalPage,
            RelationDefinitions]) -> TaskPage:
        try:
            retrieved_page = await migration_context.\
                source_datasource_info.repo.read_page(page_id)
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
        execution_context: ExecutionContext,
        ) -> Sequence[B]:
        exhausted = False
        cursor = None
        pages: List[B] = []

        while not exhausted:
            try:
                pagination = await datasource_info.repo.query_database(
                    page_id=page_id,
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
        migration_context: MigrationContext[
            PageId,
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

        if execution_context.debug:
            logger.debug("here")

        try:
            async with asyncio.TaskGroup() as tg:
                self._service_execution_context = ServiceExecutionContext(
                    task_group=tg,
                    execution_context=execution_context)

                # tg.create_task(
                #     timed(
                #         self.process_source_recursive(
                #             root_page,
                #             level,
                #             collected,
                #             migration_context,
                #             execution_context
                #         ),
                #         root_page,
                #         "root_page",
                #     )
                # )
                tg.create_task(
                        self.process_source_recursive(
                            root_page,
                            level,
                            collected,
                            migration_context,
                            execution_context
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
        relation: RelationDefinitions,
        execution_context: ExecutionContext,
    ) -> Task[Sequence[B]]:
        return self._service_execution_context.task_group.create_task(
            # timed(
            #     self.query_database(
            #         page_id=page.Id,
            #         relation=relation,
            #         datasource_info=datasource_info,
            #         execution_context=execution_context
            #     ),
            #     page,
            #     "query_database:sub_pages",
            # ),
            self.query_database(
                page_id=page.Id,
                execution_context=execution_context,
                relation=relation,
                datasource_info=datasource_info
            ),
        )

    async def process_source_recursive(
        self,
        page: TaskPage,
        level: int,
        collected: List[TaskPage],
        migration_context: MigrationContext[
            PageId,
            TaskPage,
            JournalPage,
            RelationDefinitions],
        execution_context: ExecutionContext,
    ):
        try:
            # create the coroutines and run them concurrently with timing & rate limited
            task_subpages_tasks: Task[Sequence[TaskPage]] = self.create_task_sub_pages(
                page=page,
                datasource_info=migration_context.source_datasource_info,
                relation=TaskRelationsDefinition.ANCESTORS,
                execution_context=execution_context
            )

            journal_pages_tasks: Task[Sequence[JournalPage]] = self.create_task_sub_pages(
                page=page,
                datasource_info=migration_context.journal_datasource_info,
                relation=migration_context.junction_relation_definition,
                execution_context=execution_context
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
            logger.exception("Failed to recurse for page: %s", page.Properties.Title)
            raise ServiceError(f"Failed to recurse for page: {page.Properties.Title}") from e

    async def process_journal_recursive(
        self,
        page: JournalPage,
        migration_context: MigrationContext[
            PageId,
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
            PageId,
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
            PageId,
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
            PageId,
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

    async def verify_page_migration(
        self,
        page: CommonPage,
        migration_context: MigrationContext[PageId, TaskPage, JournalPage, RelationDefinitions],
        execution_context: ExecutionContext) -> bool:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def migrate_all_pages(
        self,
        migration_context: MigrationContext[PageId, TaskPage, JournalPage, RelationDefinitions],
        execution_context: ExecutionContext) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )
