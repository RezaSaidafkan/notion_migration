import asyncio
import logging
from collections.abc import Coroutine
from functools import singledispatchmethod
from typing import Any, Awaitable, List, Sequence, Union, cast

from common_libs.constants.literal_definitions import (
    JournalRelationsDefinition,
    RelationDefinitions,
    TaskRelationsDefinition,
)
from common_libs.models.client_models import (
    BasePage,
    C,
    CommonPage,
    JournalPage,
    JournalRelation,
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
                         CommonPage,
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
        datasource_info: DatasourceInfo[BasePage, C, RelationDefinitions],
        execution_context: ExecutionContext,
        ) -> Sequence[C]:
        exhausted = False
        cursor = None
        pages: List[C] = []
        max_cursor_retries = 3
        cursor_retry_count = 0

        while not exhausted:
            try:
                if execution_context.debug:
                    logger.debug("Querying page '%s'", str(page.Id.Id))
                pagination = await datasource_info.repo.query_database(
                    page=page,
                    execution_context=execution_context,
                    data_source_id=datasource_info.datasource_id,
                    relation=relation,
                    cursor=cursor)
                pages.extend(pagination.results)
                cursor = pagination.next_cursor
                exhausted = not pagination.has_more
                cursor_retry_count = 0  # Reset retry count on success
                if execution_context.debug:
                    if exhausted:
                        logger.debug(
                            "Paginated results is exhausted '%s'", str(page.Id.Id))
                    else:
                        logger.debug(
                            "Paginating result to cursor: '%s' '%s'", cursor, str(page.Id.Id))
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
        page: CommonPage,
        migration_context: MigrationContext[
            BasePage,
            TaskPage,
            JournalPage,
            RelationDefinitions],
        execution_context: ExecutionContext,
        level: int = 0,
    ) -> None:  # pylint: disable=too-many-positional-arguments
        """Build the page hierarchy based on the schema knowledge ('Ancestor' relation) and
        delegates to the repository's generic `query_database` method.
        """
        self._service_execution_context = ServiceExecutionContext(
            execution_context=execution_context)
        await self.process_page_recursive(page, migration_context, execution_context)

    # pylint: disable=invalid-overridden-method
    # pylint: disable=too-many-positional-arguments, too-many-arguments
    def get_task_sub_pages(
        self,
        page: CommonPage,
        datasource_info: DatasourceInfo[BasePage, Any, RelationDefinitions],
        relation: RelationDefinitions,
        execution_context: ExecutionContext,
    ) -> Coroutine[Any, Any, Sequence[Union[TaskPage, JournalPage]]]:
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

    async def create_or_update_page(
        self,
        page: CommonPage,
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
        page: CommonPage,
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
        page: CommonPage,
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
        page: CommonPage,
        migration_context: MigrationContext[BasePage, TaskPage, JournalPage, RelationDefinitions],
        execution_context: ExecutionContext
    ) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def migrate_pages(
        self,
        pages: List[CommonPage],
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

    @singledispatchmethod
    async def process_page_recursive(
        self,
        page: TaskPage | JournalPage,
        migration_context: MigrationContext[
            BasePage,
            TaskPage,
            JournalPage,
            RelationDefinitions],
        execution_context: ExecutionContext,
    ) -> None:
        _, _, _ = page, migration_context, execution_context



    @process_page_recursive.register
    async def _(
        self,
        page: TaskPage,
        migration_context: MigrationContext[
            BasePage,
            TaskPage,
            JournalPage,
            RelationDefinitions],
        execution_context: ExecutionContext,
    ) -> None:
        try:
            task_subpages_tasks: Awaitable[Sequence[TaskPage]] = cast(
                Awaitable[Sequence[TaskPage]],
                self.get_task_sub_pages(
                        page=page,
                        datasource_info=migration_context.source_datasource_info,
                        relation=TaskRelationsDefinition.ANCESTORS,
                        execution_context=execution_context
                        ))

            journal_pages_tasks: Awaitable[Sequence[JournalPage]] = cast(
                Awaitable[Sequence[JournalPage]],
                self.get_task_sub_pages(
                        page=page,
                        datasource_info=migration_context.journal_datasource_info,
                        relation=migration_context.junction_relation_definition,
                        execution_context=execution_context
                        )
            )

            results_subpages, results_journal_pages = await asyncio.gather(
                task_subpages_tasks, journal_pages_tasks, return_exceptions=True
            )

            if not isinstance(results_journal_pages, BaseException) and results_journal_pages != []:
                if execution_context.debug:
                    logger.debug("Processing Journals")
                self.assign_relationships(page, results_journal_pages)
                _ = await asyncio.gather(
                    *[self.process_page_recursive(
                        journ_page,
                        migration_context,
                        execution_context)
                    for journ_page in results_journal_pages],
                    return_exceptions=True)

            if not isinstance(results_subpages, BaseException) and results_subpages != []:
                if execution_context.debug:
                    logger.debug("Processing Subpages")
                self.assign_relationships(page, results_subpages)
                _ = await asyncio.gather(
                    *[self.process_page_recursive(
                        sub_page,
                        migration_context,
                        execution_context)
                    for sub_page in results_subpages],
                    return_exceptions=True)

        except (RepositoryError, ServiceError):
            logger.exception("Failed to recurse for page: %s", page.Properties.Title)


    @process_page_recursive.register
    async def _(
        self,
        page: JournalPage,
        migration_context: MigrationContext[
            BasePage,
            TaskPage,
            JournalPage,
            RelationDefinitions],
        execution_context: ExecutionContext,
    ):
        try:
            sub_journal_pages: Sequence[JournalPage] = cast(
                Sequence[JournalPage],
                await self.get_task_sub_pages(
                    page=page,
                    datasource_info=migration_context.journal_datasource_info,
                    relation=JournalRelationsDefinition.ANCESTOR,
                    execution_context=execution_context
                    )
                )

            if sub_journal_pages:
                self.assign_relationships(page, sub_journal_pages)
                await asyncio.gather(
                    *[self.process_page_recursive(
                        journ_page,
                        migration_context,
                        execution_context)
                    for journ_page in sub_journal_pages],
                    return_exceptions=True)
        except (RepositoryError, ServiceError):
            logger.exception("Failed to recurse for page: %s", page.Properties.Title)

    @singledispatchmethod
    def assign_relationships(self, page: CommonPage, sub_pages: Sequence[CommonPage]):
        """Assign relationships to a page based on its type."""
        _, _ = page, sub_pages

    @assign_relationships.register
    def _(self, page: JournalPage, sub_pages: Sequence[JournalPage]) -> None:
        page.Relations = JournalRelation(
            Descendants=sub_pages,
            Ancestors=[page],
            JunctionRelation=None)

    @assign_relationships.register
    def _(self, page: TaskPage, sub_pages: Sequence[TaskPage] | Sequence[JournalPage]) -> None:
        if page.Relations is None:
            page.Relations = TaskRelation(Descendants=None, Ancestors=None, Journals=None)

        if sub_pages and isinstance(sub_pages[0], JournalPage):
            if len(sub_pages) != 0:
                page.Relations.Journals = cast(Sequence[JournalPage], sub_pages)
        elif len(sub_pages) != 0:
            page.Relations.Descendants = cast(Sequence[TaskPage], sub_pages)
