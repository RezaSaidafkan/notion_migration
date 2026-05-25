import asyncio
import logging
from time import perf_counter
from typing import cast
from uuid import UUID, uuid4

from common_libs.constants.literal_definitions import (
    JournalRelationsDefinition,
    JunctionRelationDefinition,
    RelationDefinitions,
    TaskRelationsDefinition,
)
from common_libs.models.client_models import (
    BasePage,
    JournalPage,
    PageId,
    TaskPage,
)
from common_libs.models.context import (
    DatasourceInfo,
    ExecutionContext,
    MigrationContext,
)
from common_libs.singletons.rate_limiter_singleton import RateLimiter
from common_libs.singletons.tracing_singleton import Tracing

import migration_engine.service.service_page_notion as spn
from migration_engine.config.load_config import GLOBAL_CONFIG
from migration_engine.helpers.utils import count_leaves
from migration_engine.repo.repo_page_notion import (
    NotionRepoJournal,
    NotionRepoSource,
    RepositoryDirectInjection,
)
from migration_engine.service.service_page_interface import ServiceError

logger = logging.getLogger(__name__)

class MigrationEngineError(Exception):
    pass

# pylint: disable = too-few-public-methods
class Runner:
    def __init__(self,
                 execution_context: ExecutionContext,
                 migration_context: MigrationContext[
                     BasePage,
                     TaskPage,
                     JournalPage,
                     RelationDefinitions]):
        self._migration_context = migration_context
        self._execution_context = execution_context
        self.service = spn.ServicePage()

    async def build_page_hierarchy(
        self,
        source_parent_page_id: UUID,
    ) -> TaskPage:
        root_base_page = BasePage(Id=PageId(Id=source_parent_page_id))
        root_task_page = await self.service.read_page(
            page=root_base_page,
            execution_context=self._execution_context,
            migration_context=self._migration_context)

        await self.service.build_page_hierarchy(
            page=root_task_page,
            execution_context=self._execution_context,
            migration_context=self._migration_context)

        return root_task_page

    async def run_end_to_end_migration(self, source_parent_page_id: UUID,
    ) -> None:
        """Execute the full migration process:
        1. Builds the page hierarchy from the source.
        2. Migrates the pages to the target datasource.
        """
        logger.info("Starting end-to-end migration for page: '%s'", source_parent_page_id)
        root_page = cast(
            TaskPage,
            self.service.read_page(page=BasePage(Id=PageId(Id=source_parent_page_id)),
                                    migration_context=self._migration_context,
                                    execution_context=self._execution_context)
        )
        await self.service.migrate_page(
            page=root_page,
            migration_context=self._migration_context,
            execution_context=self._execution_context
        )

        logger.info("Migration completed successfully for page: '%s'", source_parent_page_id)


def _setup_runner() -> tuple[Runner, UUID]:
    execution_id = uuid4()

    if GLOBAL_CONFIG.debug:
        logger.debug("execution_id: '%s'", execution_id)
    _ = Tracing(address=GLOBAL_CONFIG.tracing_url,
                port=GLOBAL_CONFIG.tracing_port)
    _ = RateLimiter(max_rate=GLOBAL_CONFIG.max_rate,
                    time_period=GLOBAL_CONFIG.time_period)

    execution_context = ExecutionContext(
        execution_id=execution_id,
        debug=GLOBAL_CONFIG.debug,
        page_size=GLOBAL_CONFIG.page_size,
    )

    repository_di = RepositoryDirectInjection(
                        source_repo=NotionRepoSource(
                            GLOBAL_CONFIG.notion_api_key,
                            GLOBAL_CONFIG.notion_client_timeout_ms,
                            execution_context.debug),
                        journal_repo=NotionRepoJournal(
                            GLOBAL_CONFIG.notion_api_key,
                            GLOBAL_CONFIG.notion_client_timeout_ms,
                            execution_context.debug)
            )

    migration_context = MigrationContext(
        source_datasource_info=DatasourceInfo[BasePage, TaskPage, RelationDefinitions](
            datasource_id=GLOBAL_CONFIG.source_datasource_id,
            repo=repository_di.source_repo),

        target_datasource_info=DatasourceInfo[BasePage, TaskPage, RelationDefinitions](
            datasource_id=GLOBAL_CONFIG.target_datasource_id,
            repo=repository_di.source_repo),

        journal_datasource_info=DatasourceInfo[BasePage, JournalPage, RelationDefinitions](
            datasource_id=GLOBAL_CONFIG.journal_datasource_id,
            repo=repository_di.journal_repo),

        junction_relation_definition=JunctionRelationDefinition(
            GLOBAL_CONFIG.junction_relation_definition),
        task_relation_definition=TaskRelationsDefinition.ANCESTORS,
        journal_relation_definition=JournalRelationsDefinition.ANCESTOR
        )

    runner = Runner(execution_context, migration_context)
    return runner, execution_id


async def end_to_end_migration():
    runner, execution_id = _setup_runner()
    try:
        await runner.run_end_to_end_migration(
            source_parent_page_id=GLOBAL_CONFIG.source_parent_page_id
        )

    except KeyError:
        raise MigrationEngineError(
            f"Failed to get proper input from environment variables \
                for execution_id: {execution_id}") from None
    except ServiceError as me:
        raise MigrationEngineError(
            f"An error happened executing Migration Engine for \
                execution_id: {execution_id}") from me


async def build_page_hierarchy():
    runner, execution_id = _setup_runner()
    try:
        root_task_page = await runner.build_page_hierarchy(
            source_parent_page_id=GLOBAL_CONFIG.source_parent_page_id
        )
        logger.info("Root Page Hierarchy:\nLeaves Count:%s",
                    count_leaves(root_task_page))

    except KeyError:
        raise MigrationEngineError(
            f"Failed to get proper input from environment variables \
                for execution_id: {execution_id}") from None
    except ServiceError as me:
        raise MigrationEngineError(
            f"An error happened executing Migration Engine for \
                execution_id: {execution_id}") from me


def run_end_to_end_migration():
    start_time = perf_counter()
    logging.basicConfig(
        level=logging.DEBUG if GLOBAL_CONFIG.debug else logging.INFO,
        format="%(levelname)s [%(asctime)s] %(name)s - %(message)s")
    try:
        asyncio.run(end_to_end_migration())
    finally:
        end_time = perf_counter()
        logger.info("Asynchronous Execution time: %d seconds", end_time - start_time)


def run_build_page_hierarchy():
    start_time = perf_counter()
    logging.basicConfig(
        level=logging.DEBUG if GLOBAL_CONFIG.debug else logging.INFO,
        format="%(levelname)s [%(asctime)s] %(name)s - %(message)s")
    try:
        asyncio.run(build_page_hierarchy())
    finally:
        end_time = perf_counter()
        logger.info("Asynchronous Execution time: %d seconds", end_time - start_time)
