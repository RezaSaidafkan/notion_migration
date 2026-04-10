import asyncio
import logging
from collections.abc import Coroutine
from typing import Any, Awaitable, List, Sequence

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
        except RepositoryError as re:
            raise ServiceError(
                f"Failed to read page_id: {page}") from re

    # pylint: disable=invalid-overridden-method, too-many-locals
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
        max_cursor_retries = 3
        cursor_retry_count = 0

        while not exhausted:
            try:
                if execution_context.debug:
                    logger.debug("Querying page '%s'", str(page.Id))
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
                cursor_retry_count = 0  # Reset retry count on success
                if execution_context.debug:
                    if exhausted:
                        logger.debug(
                            "Paginated results is exhausted '%s'", str(page.Id))
                    else:
                        logger.debug(
                            "Paginating result to cursor: '%s' '%s'", cursor, str(page.Id))
            except RepositoryError as re:
                # Check if this is a cursor-related error
                error_msg = str(re).lower()
                is_cursor_error = "cursor" in error_msg and "start_cursor" in error_msg

                if is_cursor_error and cursor_retry_count < max_cursor_retries:
                    # Cursor has expired, restart from the beginning
                    cursor_retry_count += 1
                    logger.warning(
                        "Cursor expired, restarting pagination from beginning (attempt %d/%d)",
                        cursor_retry_count, max_cursor_retries
                    )
                    cursor = None
                    # Don't include previous partial results - restart completely
                    pages = []
                    continue

                error_msg_detail = \
                    f"Failed to query database: '{datasource_info}', \
                      page: '{page.Id}',\
                      {str(re.args)}"

                if cursor:
                    cursor_msg = f" at cursor: '{cursor}'"
                    error_msg_detail = error_msg_detail + cursor_msg

                raise ServiceError(error_msg_detail).with_traceback(re.__traceback__) from re
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

        self._service_execution_context = ServiceExecutionContext(
            execution_context=execution_context)

        _ = await asyncio.gather(
                self.process_source_recursive(
                    page,
                    level,
                    collected,
                    migration_context,
                    execution_context
                    )
                )
        return collected

    # pylint: disable=invalid-overridden-method
    # pylint: disable=too-many-positional-arguments, too-many-arguments
    def get_task_sub_pages(
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
        if execution_context.debug:
            logger.debug("Processing sub page '%s'", str(page.Id.Id))
        try:
            return self.query_database(
                page=BasePage(Id=page.Id),
                execution_context=execution_context,
                relation=relation,
                datasource_info=datasource_info
            )
        except ServiceError as se:
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
            task_subpages_tasks: Awaitable[Sequence[TaskPage]] = self.get_task_sub_pages(
                        page=page,
                        datasource_info=migration_context.source_datasource_info,
                        relation=TaskRelationsDefinition.ANCESTORS,
                        execution_context=execution_context
                        )

            journal_pages_tasks: Awaitable[Sequence[JournalPage]] = self.get_task_sub_pages(
                        page=page,
                        datasource_info=migration_context.journal_datasource_info,
                        relation=migration_context.junction_relation_definition,
                        execution_context=execution_context
                        )

            results_subpages, results_journal_pages = await asyncio.gather(
                task_subpages_tasks, journal_pages_tasks, return_exceptions=True
            )

            page.Relations = TaskRelation(Descendants=None, Ancestors=None, Journals=None)

            if not isinstance(results_journal_pages, BaseException) and results_journal_pages != []:
                if execution_context.debug:
                    logger.debug("Processing Journals")
                page.Relations.Journals = results_journal_pages
                _ = await asyncio.gather(
                    *[self.process_journal_recursive(
                        journ_page,
                        migration_context,
                        execution_context)
                    for journ_page in results_journal_pages],
                    return_exceptions=True)

            if not isinstance(results_subpages, BaseException) and results_subpages != []:
                if execution_context.debug:
                    logger.debug("Processing Subpages")
                page.Relations.Descendants = results_subpages
                _ = await asyncio.gather(
                    *[self.process_source_recursive(
                        sub_page,
                        level + 1,
                        collected,
                        migration_context,
                        execution_context)
                    for sub_page in results_subpages],
                    return_exceptions=True)

            if level == 1 and self._service_execution_context.execution_context.debug:
                logger.debug("The page hierarchy created")
                collected.append(page)
        except (RepositoryError, ServiceError):
            logger.exception("Failed to recurse for page: %s", page.Properties.Title)

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
        sub_journal_pages: Sequence[JournalPage] = await self.get_task_sub_pages(
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

            _ = await asyncio.gather(
                *[self.process_journal_recursive(
                    journ_page,
                    migration_context,
                    execution_context)
                  for journ_page in sub_journal_pages],
                return_exceptions=True)

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
