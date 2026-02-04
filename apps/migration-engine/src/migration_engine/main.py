import asyncio
import logging
from time import perf_counter
from typing import Union
from uuid import UUID

from common_libs.constants.literal_definitions import (
    DatasourceInfo,
    ExecutionContext,
    JournalJunctionRelations,
    MigrationContext,
)
from common_libs.models.client_models import (
    JournalPage,
    JournalRelation,
    Page,
    PageId,
    PageRelation,
)
from pydantic import ValidationError

import migration_engine.service.service_page_notion as spn
from migration_engine.config.load_config import GLOBAL_CONFIG
from migration_engine.helpers.utils import count_leaves
from migration_engine.repo.repo_page_notion import NotionRepoJournalPage, NotionRepoPage
from migration_engine.service.service_page_interface import ServiceError

logger = logging.getLogger(__name__)

PageType = Union[Page, JournalPage]
DatabaseType = Union[Page, JournalPage]
RelationType = Union[PageRelation, JournalRelation]

class MigrationEngineError(Exception):
    pass

# pylint: disable = too-few-public-methods
class Runner:
    def __init__(self, execution_context: ExecutionContext, migration_context: MigrationContext):
        repo_notion_source = NotionRepoPage(
            migration_context.NOTION_API_KEY,
            execution_context.DEBUG)
        repo_notion_journal = NotionRepoJournalPage(
            migration_context.NOTION_API_KEY,
            execution_context.DEBUG)
        self.service = spn.ServicePage[
            PageId,
            PageType,
            DatabaseType,
            RelationType](
                repo_journal=repo_notion_journal,
                repo_source=repo_notion_source
            )
        self._execution_context = execution_context
        self._migration_context = migration_context
        logging.basicConfig(
            level=logging.DEBUG if execution_context.DEBUG else logging.INFO)

    async def run(
        self,
        source_parent_page_id: UUID,
    ) -> None:
        try:
            root_page_id = PageId(Id=source_parent_page_id)
            root_page = await self.service.read_page(root_page_id)

            _ = await self.service.build_page_hierarchy(
                migration_context=self._migration_context,
                execution_context=self._execution_context,
                root_page=root_page,
            )
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
        migration_context = MigrationContext(
            NOTION_API_KEY=GLOBAL_CONFIG.notion_api_key,
            SOURCE_DATASOURCE_INFO=DatasourceInfo(
                DatasourceId=GLOBAL_CONFIG.source_datasource_id),
            TARGET_DATASOURCE_INFO=DatasourceInfo(
                GLOBAL_CONFIG.target_datasource_id),
            JOURNAL_DATASOURCE_INFO=DatasourceInfo(
                DatasourceId=GLOBAL_CONFIG.journal_datasource_id),
            JOURNAL_JUNCTION_RELATION=JournalJunctionRelations(
                GLOBAL_CONFIG.journal_junction_relation)
            )

        execution_context = ExecutionContext(
            DEBUG=GLOBAL_CONFIG.debug,
            PAGE_SIZE=GLOBAL_CONFIG.page_size
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
