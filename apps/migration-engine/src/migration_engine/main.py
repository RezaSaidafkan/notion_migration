import asyncio
import logging
from time import perf_counter
from typing import Union
from uuid import UUID

from common_libs.constants.literal_definitions import DatasourceInfo, JournalRelations
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

logger = logging.getLogger(__name__)

PageType = Union[Page, JournalPage]
DatabaseType = Union[Page, JournalPage]
RelationType = Union[PageRelation, JournalRelation]


# pylint: disable = too-few-public-methods
class Runner:
    def __init__(self):
        repo_notion_source = NotionRepoPage(GLOBAL_CONFIG.notion_api_key)
        repo_notion_journal = NotionRepoJournalPage(GLOBAL_CONFIG.notion_api_key)
        self.service = spn.ServicePage[PageId, PageType, DatabaseType, RelationType](
            repo_journal=repo_notion_journal, repo_source=repo_notion_source
        )

    async def run(
        self,
        source_datasource_info: DatasourceInfo,
        journal_datasource_info: DatasourceInfo,
        source_parent_page_id: UUID,
        journal_relation: JournalRelations,
    ) -> None:
        try:
            root_page_id = PageId(Id=source_parent_page_id)
            root_page = await self.service.read_page(root_page_id)

            _ = await self.service.build_page_hierarchy(
                root_page=root_page,
                source_datasource_info=source_datasource_info,
                journal_datasource_info=journal_datasource_info,
                journal_relation=journal_relation,
            )
            logger.info("Root Page Hierarchy:\n%s\nLeaves Count:%s",
                        root_page, count_leaves(root_page))
        except ValidationError as page_id_e:
            logger.exception("Failed to validate PageId: %s: %s", source_parent_page_id, page_id_e)
            raise page_id_e
        except Exception as e:
            logger.exception("Unknown error happened: %s", e)
            raise e


async def execute_lifestyle():
    runner = Runner()
    journal_relation = JournalRelations.LIFE_STYLE
    journal_datasource_info = DatasourceInfo(DatasourceId=GLOBAL_CONFIG.journal_datasource_id)
    source_datasource_info = DatasourceInfo(
        DatasourceId=GLOBAL_CONFIG.source_datasource_id
    )
    await runner.run(
        source_parent_page_id=GLOBAL_CONFIG.source_parent_page_id,
        source_datasource_info=source_datasource_info,
        journal_datasource_info=journal_datasource_info,
        journal_relation=journal_relation,
    )

def main():
    start_time = perf_counter()
    asyncio.run(execute_lifestyle())
    end_time = perf_counter()
    print(f"Asynchronous Execution time: {end_time - start_time} seconds")


if __name__ == "__main__":
    main()
