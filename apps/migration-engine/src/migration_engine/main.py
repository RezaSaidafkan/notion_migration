import asyncio
import logging
from time import perf_counter
from uuid import UUID

from common_libs.constants.literal_definitions import (
    ExecutionContext,
    JournalRelationsDefinition,
    JunctionRelationDefinition,
    RelationDefinitions,
    TaskRelationsDefinition,
)
from common_libs.models.client_models import (
    DatasourceInfo,
    JournalPage,
    MigrationContext,
    PageId,
    TaskPage,
)
from pydantic import ValidationError

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
                     PageId,
                     TaskPage,
                     JournalPage,
                     RelationDefinitions]):
        self.service = spn.ServicePage(execution_context, migration_context)

        logging.basicConfig(
            level=logging.DEBUG if execution_context.DEBUG else logging.INFO)

    async def run(
        self,
        source_parent_page_id: UUID,
    ) -> None:
        try:
            root_page_id = PageId(Id=source_parent_page_id)
            root_page = await self.service.read_page(root_page_id)

            _ = await self.service.build_page_hierarchy(root_page=root_page)

            logger.info("Root Page Hierarchy:\n%s\nLeaves Count:%s",
                        root_page, count_leaves(root_page))
        except ValidationError as page_id_e:
            logger.exception("Failed to validate PageId: %s: %s",
                             source_parent_page_id, page_id_e)
            raise page_id_e
        except Exception as e:
            logger.exception("Unknown error happened: %s", e)
            raise e


async def execute_migration_engine():
    try:

        execution_context = ExecutionContext(
            DEBUG=GLOBAL_CONFIG.debug,
            PAGE_SIZE=GLOBAL_CONFIG.page_size
        )

        repository_di = RepositoryDirectInjection(
                            source_repo=NotionRepoSource(
                                GLOBAL_CONFIG.notion_api_key,
                                execution_context.DEBUG),
                            journal_repo=NotionRepoJournal(
                                GLOBAL_CONFIG.notion_api_key,
                                execution_context.DEBUG)
                )

        migration_context = MigrationContext(
            SOURCE_DATASOURCE_INFO=DatasourceInfo[PageId, TaskPage, RelationDefinitions](
                DatasourceId=GLOBAL_CONFIG.source_datasource_id,
                Repo=repository_di.source_repo),

            TARGET_DATASOURCE_INFO=DatasourceInfo[PageId, TaskPage, RelationDefinitions](
                DatasourceId=GLOBAL_CONFIG.target_datasource_id,
                Repo=repository_di.source_repo),

            JOURNAL_DATASOURCE_INFO=DatasourceInfo[PageId, JournalPage, RelationDefinitions](
                DatasourceId=GLOBAL_CONFIG.journal_datasource_id,
                Repo=repository_di.journal_repo),

            JUNCTION_RELATION_DEFINITION=JunctionRelationDefinition(
                GLOBAL_CONFIG.junction_relation_definition),
            TASK_RELATION_DEFINITION=TaskRelationsDefinition.ANCESTORS,
            JOURNAL_RELATION_DEFINITION=JournalRelationsDefinition.ANCESTOR
            )

        runner = Runner(execution_context, migration_context)

        await runner.run(
            source_parent_page_id=GLOBAL_CONFIG.source_parent_page_id
        )
    except KeyError as ke:
        raise MigrationEngineError(
            "Failed to get proper input from environment variables") from ke
    except ServiceError as se:
        raise MigrationEngineError(
            "An error happened executing Migration Engine") from se


def main():
    start_time = perf_counter()
    asyncio.run(execute_migration_engine())
    end_time = perf_counter()
    print(f"Asynchronous Execution time: {end_time - start_time} seconds")


if __name__ == "__main__":
    main()
