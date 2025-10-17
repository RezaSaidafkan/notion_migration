import src.service.service_page_notion as spn
from src.constants.literal_definitions import DatabaseName, JournalName, SourceParentPageId
import src.repo.repo_page_notion as rpn
from src.models.client_models import ClientPage
from typing import List
import asyncio
from time import perf_counter
from src.config.load_config import GLOBAL_CONFIG



class Runner:
    def __init__(self):
        repo_notion = rpn.NotionClientAPI(GLOBAL_CONFIG.NOTION_API_KEY)
        self.service = spn.ServicePage(repo=repo_notion)

    async def run(self, 
                  parent_page_id: str, 
                  source_database_id: str, 
                  source_database_name: DatabaseName, 
                  journal_database_id: str,
                  journal_db_name: JournalName.JOURNAL) -> List[ClientPage]:
        root_page = await self.service.get_page(parent_page_id, source_database_name)
        _ = await self.service.build_page_hierarchy(root_page, source_database_id, source_database_name, journal_database_id, journal_db_name)

async def main():
    runner = Runner()
    source_database_name = DatabaseName.LIFE_STYLE
    await runner.run(
        parent_page_id=GLOBAL_CONFIG.SOURCE_PARENT_PAGE,
        source_database_id=GLOBAL_CONFIG.SOURCE_DATABASE_ID,
        source_database_name=source_database_name,
        journal_database_id=GLOBAL_CONFIG.TARGET_DATABASE_ID,
        journal_db_name=JournalName.JOURNAL
        )

if __name__ == "__main__":
    start_time = perf_counter()
    asyncio.run(main())
    end_time = perf_counter()
    print(f"Asynchronous Execution time: {end_time - start_time} seconds")
