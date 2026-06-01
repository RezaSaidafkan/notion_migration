import asyncio
import logging
from collections.abc import Coroutine
from functools import singledispatchmethod
from typing import Any, Awaitable, Dict, List, Sequence, Tuple, Union, cast

from common_libs.constants.literal_definitions import (
    JournalRelationsDefinition,
    RelationDefinitions,
    TaskRelationsDefinition,
)
from common_libs.models.client_models import (
    Ancestors,
    BasePage,
    C,
    CommonPage,
    Descendants,
    JournalPage,
    Journals,
    PageId,
    RelativePages,
    TaskPage,
)
from common_libs.models.context import (
    DatasourceInfo,
    ExecutionContext,
    MigrationContext,
)
from common_libs.utils.tracing import tracer
from marshmallow import ValidationError

from migration_engine.repo.repo_page_interface import (
    RepositoryError,
)
from migration_engine.service.service_page_interface import (
    ServiceError,
    ServiceExecutionContext,
    ServicePageInterface,
)

logger = logging.getLogger(__name__)

SOURCE_PAGES: Dict[PageId, TaskPage | JournalPage | None] = {}
TARGET_PAGES: Dict[PageId, TaskPage | JournalPage | None] = {}
MIGRATION_TABLE: Dict[PageId, PageId | None] = {}



class ServicePage(
    ServicePageInterface[BasePage,
                         CommonPage,
                         TaskPage,
                         JournalPage,
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
                source_datasource_info.repo.read_page(page, execution_context)
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
        page: TaskPage | JournalPage,
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
        page = cast(TaskPage, page)
        self._service_execution_context = ServiceExecutionContext(
            execution_context=execution_context)
        SOURCE_PAGES[page.Id] = page
        # migrate route page
        target_task_page: TaskPage = cast(
            TaskPage,
            await self.migrate_page(
                page=page,
                migration_context=migration_context,
                execution_context=execution_context
                )
            )
        if not isinstance(target_task_page, BaseException):
            TARGET_PAGES[target_task_page.Id] = target_task_page
            MIGRATION_TABLE[page.Id] = target_task_page.Id
            await self.process_page_recursive(
                page,
                migration_context,
                execution_context)
        else:
            raise ServiceError("Failed to migrate route page.")

    # pylint: disable=invalid-overridden-method
    # pylint: disable=too-many-positional-arguments, too-many-arguments
    @tracer
    def get_task_sub_pages(
        self,
        page: CommonPage,
        datasource_info: DatasourceInfo[BasePage, Any, RelationDefinitions],
        execution_context: ExecutionContext,
        relation: RelationDefinitions,
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
            CommonPage,
            CommonPage,
            RelationDefinitions],
        execution_context: ExecutionContext) -> bool:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def add_relations_to_page(
        self,
        page: TaskPage | JournalPage,
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

    @tracer
    async def migrate_page(
        self,
        page: TaskPage | JournalPage,
        migration_context: MigrationContext[BasePage, TaskPage, JournalPage, RelationDefinitions],
        execution_context: ExecutionContext
    ) -> TaskPage | JournalPage:
        page = cast(TaskPage, page)
        try:
            created_page = await migration_context.target_datasource_info.repo.create_page(
                page=page,
                execution_context=execution_context,
                parent_page_id=migration_context.target_datasource_info.datasource_id)
            return created_page
        except RepositoryError as re:
            raise ServiceError(
                f"Failed to migrate page: '{page.Id.Id}'",
            ) from re


    async def load_pages(
        self,
        pages: List[TaskPage | JournalPage],
        migration_context: MigrationContext[BasePage, TaskPage, JournalPage, RelationDefinitions],
        execution_context: ExecutionContext
    ):
        target_pages_results = await asyncio.gather(
            *[self.migrate_page(
                page=sub_page,
                migration_context=migration_context,
                execution_context=execution_context)
              for sub_page in pages],
            return_exceptions=True)
        for source_page, target_page in zip(pages, target_pages_results):
            SOURCE_PAGES[source_page.Id] = source_page
            if isinstance(target_page, BaseException):
                MIGRATION_TABLE[source_page.Id] = None
                if execution_context.debug:
                    logger.debug("Failed to migrate %s", source_page.Id)
            else:
                TARGET_PAGES[target_page.Id] = target_page
                if execution_context.debug:
                    logger.debug("Migrated %s to %s", source_page.Id, target_page.Id)
                MIGRATION_TABLE[source_page.Id] = target_page.Id

    async def verify_page_migration(
        self,
        page: BasePage,
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
    @tracer
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
            # 1. Extract Stage
            # read relevant pages to the route page
            if execution_context.debug:
                logger.debug(
                    "Getting level pages for page: %s %s",
                    str(page.Id),
                    page.Properties.Title)
            target_task_page, task_subpages, task_journal_pages = await self._extract_level_pages(
                page=page,
                migration_context=migration_context,
                execution_context=execution_context,
            )

            sync_tasks: List[Awaitable[Any]] = []

            if task_journal_pages:
                _update_source_table(task_journal_pages)
                self.assign_relationships(page, task_journal_pages)

                sync_tasks.extend(
                    [self.process_page_recursive(
                        journal_page,
                        migration_context,
                        execution_context)
                    for journal_page in task_journal_pages])

            if task_subpages:
                if execution_context.debug:
                    logger.debug(
                        "Getting sub pages for page: %s %s",
                        str(page.Id),
                        page.Properties.Title)
                _update_source_table(task_subpages)
                self.assign_relationships(page, task_subpages)

                # 3. Load Stage
                # load sub pages
                if execution_context.debug:
                    logger.debug("Migrating sub pages for page: %s", str(page.Id))
                await self.load_pages(
                    pages=list(task_subpages),
                    migration_context=migration_context,
                    execution_context=execution_context)

                # assign & load relations between target pages
                if target_task_page:
                    sync_tasks.append(
                        self._get_task_load_relation(
                            page=target_task_page,
                            migration_context=migration_context,
                            execution_context=execution_context,
                            task_subpages=task_subpages,
                            )
                        )
                sync_tasks.extend(
                    [self.process_page_recursive(
                        sub_page,
                        migration_context,
                        execution_context,
                        )
                    for sub_page in task_subpages])

                # what if target_task_page_relation_task fails?
                # tracing table flow should take care of it
                _ = await asyncio.gather(
                    *sync_tasks,
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
        if page.Properties.Descendants is None:
            page.Properties.Descendants = Descendants(Items=list(sub_pages))
        if page.Properties.Ancestors is None:
            page.Properties.Ancestors = Ancestors(Items=[page])
        if page.Properties.JunctionRelation is None:
            # to be implemented later on
            page.Properties.JunctionRelation = None

    @assign_relationships.register
    def _(self, page: TaskPage, sub_pages: Sequence[TaskPage] | Sequence[JournalPage]) -> None:
        try:
            if sub_pages and isinstance(sub_pages[0], JournalPage):
                if len(sub_pages) != 0:
                    if page.Properties.Journals is None:
                        page.Properties.Journals = Journals(Items=list(sub_pages))
                    else:
                        page.Properties.Journals.Items.extend(sub_pages)
            if sub_pages and isinstance(sub_pages[0], TaskPage):
                if len(sub_pages) != 0:
                    for sub_page in sub_pages:
                        if sub_page.Properties.Ancestors is None:
                            sub_page.Properties.Ancestors = Ancestors(Items=[page])
                        else:
                            sub_page.Properties.Ancestors.Items.extend(sub_pages)

                    if page.Properties.Descendants is None:
                        page.Properties.Descendants = Descendants(Items=list(sub_pages))
                    else:
                        page.Properties.Descendants.Items.extend(sub_pages)
        except ValidationError:
            raise ServiceError("Failed to assign relationships.") from None

    @tracer
    async def _extract_level_pages(
        self,
        page: TaskPage | JournalPage,
        migration_context: MigrationContext[
            BasePage,
            TaskPage,
            JournalPage,
            RelationDefinitions],
        execution_context: ExecutionContext,
        ) -> Tuple[TaskPage | None, Sequence[TaskPage] | None, Sequence[JournalPage] | None]:
        target_task_page: TaskPage | None = None
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

        if MIGRATION_TABLE.get(page.Id) is None:
            target_task_page_task: Awaitable[TaskPage] = cast(
                Awaitable[TaskPage],
                self.migrate_page(
                    page=page,
                    migration_context=migration_context,
                    execution_context=execution_context
                    )
                )

            target_task_page_result, subpages_results_result, journal_pages_results_result = \
                await asyncio.gather(
                    target_task_page_task,
                    task_subpages_tasks,
                    journal_pages_tasks,
                    return_exceptions=True)

            if not isinstance(subpages_results_result, BaseException):
                task_subpages = subpages_results_result
            else:
                task_subpages = None

            if not isinstance(journal_pages_results_result, BaseException):
                task_journal_pages = journal_pages_results_result
            else:
                task_journal_pages = None

            if not isinstance(target_task_page_result, BaseException):
                target_task_page = target_task_page_result
                _update_target_table([target_task_page])
                _update_migration_table([(page, target_task_page)])
            else:
                TARGET_PAGES[page.Id] = None
        else:
            target_task_page_id = MIGRATION_TABLE[page.Id]
            target_task_page = cast(
                TaskPage,
                TARGET_PAGES.get(target_task_page_id, None)
                ) if target_task_page_id is not None else None
            subpages_results_result, journal_pages_results_result = await asyncio.gather(
                task_subpages_tasks,
                journal_pages_tasks,
                return_exceptions=True)

            if not isinstance(subpages_results_result, BaseException):
                task_subpages = subpages_results_result
            else:
                task_subpages = None

            if not isinstance(journal_pages_results_result, BaseException):
                task_journal_pages = journal_pages_results_result
            else:
                task_journal_pages = None

        return target_task_page, task_subpages, task_journal_pages

    @tracer
    def _get_task_load_relation(
        self,
        page: TaskPage,
        migration_context: MigrationContext[
            BasePage,
            TaskPage,
            JournalPage,
            RelationDefinitions],
        execution_context: ExecutionContext,
        task_subpages: Sequence[TaskPage],
        ) -> Coroutine[Any, Any, bool]:
        target_relations: List[TaskPage | JournalPage] = []
        for sub_page in task_subpages:
            target_task_page_id = MIGRATION_TABLE[sub_page.Id]
            if target_task_page_id is None:
                continue
            target_page = TARGET_PAGES.get(target_task_page_id)
            if target_page is not None:
                target_relations.append(target_page)

        self.assign_relationships(page, target_relations)
        target_task_page_relation_task: Coroutine[Any, Any, bool] = \
            migration_context.target_datasource_info.repo.update_page(
                page=page,
                execution_context=execution_context
        )
        return target_task_page_relation_task

def _update_source_table(pages: Sequence[TaskPage | JournalPage]):
    for page in pages:
        SOURCE_PAGES[page.Id] = page

def _update_migration_table(pages: Sequence[Tuple[TaskPage | JournalPage, TaskPage | JournalPage]]):
    for source_page, target_page in pages:
        MIGRATION_TABLE[source_page.Id] = target_page.Id

def _update_target_table(pages: Sequence[TaskPage | JournalPage]):
    for page in pages:
        TARGET_PAGES[page.Id] = page
