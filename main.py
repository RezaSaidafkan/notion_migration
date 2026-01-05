import asyncio
import pprint
from time import perf_counter
from typing import Union

import src.service.service_page_notion as spn
from src.config.load_config import GLOBAL_CONFIG
from src.constants.literal_definitions import DatabaseInfo, JournalRelations
from src.helpers.utils import count_leaves
from src.models.client_models import (
    JournalPage,
    JournalRelation,
    Page,
    PageId,
    PageRelation,
)
from src.repo.repo_page_notion import NotionRepoJournalPage, NotionRepoPage

PageType = Union[Page, JournalPage]
DatabaseType = Union[Page, JournalPage]
RelationType = Union[PageRelation, JournalRelation]


class Runner:
    def __init__(self):
        repo_notion_source = NotionRepoPage(GLOBAL_CONFIG.notion_api_key)
        repo_notion_journal = NotionRepoJournalPage(GLOBAL_CONFIG.notion_api_key)
        self.service = spn.ServicePage[PageId, PageType, DatabaseType, RelationType](
            repo_journal=repo_notion_journal, repo_source=repo_notion_source
        )

    async def run(
        self,
        parent_page_id: str,
        source_database: DatabaseInfo,
        journal_database: DatabaseInfo,
        journal_relation: JournalRelations,
    ) -> None:
        root_page_id = PageId(Id=parent_page_id)
        root_page = await self.service.refresh_from_backend(root_page_id)

        _ = await self.service.build_page_hierarchy(
            root_page=root_page,
            source_database=source_database,
            journal_database=journal_database,
            journal_relation=journal_relation,
        )
        pprint.pprint(root_page)
        pprint.pprint(count_leaves(root_page))


async def main():
    runner = Runner()
    journal_relation = JournalRelations.LIFE_STYLE
    journal_db = DatabaseInfo(DatabaseId=GLOBAL_CONFIG.journal_database_id)
    source_db = DatabaseInfo(DatabaseId=GLOBAL_CONFIG.source_database_id_life_style)
    await runner.run(
        parent_page_id=GLOBAL_CONFIG.source_parent_page,
        source_database=source_db,
        journal_database=journal_db,
        journal_relation=journal_relation,
    )


if __name__ == "__main__":
    start_time = perf_counter()
    asyncio.run(main())
    end_time = perf_counter()
    print(f"Asynchronous Execution time: {end_time - start_time} seconds")
