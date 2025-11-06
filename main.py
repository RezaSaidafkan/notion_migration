import src.service.service_page_notion as spn
from src.constants.literal_definitions import JournalRelations, DatabaseInfo
from src.repo.repo_page_notion import NotionRepoJournalPage, NotionRepoPage
from src.models.client_models import PageId
import asyncio
from time import perf_counter
from src.config.load_config import GLOBAL_CONFIG
import pprint
from typing import Union
from src.models.client_models import Page, JournalPage, PageRelation, JournalRelation
from src.helpers.utils import count_leaves

PageType = Union[Page, JournalPage]
DatabaseType = Union[Page, JournalPage]
RelationType = Union[PageRelation, JournalRelation]

class Runner:
    def __init__(self):
        repo_notion_source = NotionRepoPage(GLOBAL_CONFIG.NOTION_API_KEY)
        repo_notion_journal = NotionRepoJournalPage(GLOBAL_CONFIG.NOTION_API_KEY)
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
    journal_db = DatabaseInfo(DatabaseId=GLOBAL_CONFIG.JOURNAL_DATABASE_ID)
    source_db = DatabaseInfo(DatabaseId=GLOBAL_CONFIG.SOURCE_DATABASE_ID_LIFE_STYLE)
    await runner.run(
        parent_page_id=GLOBAL_CONFIG.SOURCE_PARENT_PAGE,
        source_database=source_db,
        journal_database=journal_db,
        journal_relation=journal_relation,
    )


if __name__ == "__main__":
    start_time = perf_counter()
    asyncio.run(main())
    end_time = perf_counter()
    print(f"Asynchronous Execution time: {end_time - start_time} seconds")
