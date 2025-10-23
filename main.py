import src.service.service_page_notion as spn
from src.constants.literal_definitions import JournalRelations
import src.repo.repo_page_notion as rpn
from src.models.client_models import CommonPage
from typing import List
import asyncio
from time import perf_counter
from src.config.load_config import GLOBAL_CONFIG
import pprint



class Runner:
    def __init__(self):
        repo_notion = rpn.NotionClientAPI(GLOBAL_CONFIG.NOTION_API_KEY)
        self.service = spn.ServicePage(repo=repo_notion)

    async def run(self, 
                  parent_page_id: str, 
                  source_database_id: str, 
                  journal_database_id: str,
                  journal_relation: JournalRelations
                  ) -> List[CommonPage]:
        root_page = await self.service.get_source_page(parent_page_id)
        
        _ = await self.service.build_page_hierarchy(
            root_page=root_page,
            source_database_id=source_database_id,
            journal_database_id=journal_database_id,
            journal_relation=journal_relation
            )
        pprint.pprint(root_page)

async def main():
    runner = Runner()
    journal_relation = JournalRelations.LIFE_STYLE
    await runner.run(
        parent_page_id=GLOBAL_CONFIG.SOURCE_PARENT_PAGE,
        source_database_id=GLOBAL_CONFIG.SOURCE_DATABASE_ID,
        journal_database_id=GLOBAL_CONFIG.JOURNAL_DATABASE_ID,
        journal_relation=journal_relation
        )

if __name__ == "__main__":
    start_time = perf_counter()
    asyncio.run(main())
    end_time = perf_counter()
    print(f"Asynchronous Execution time: {end_time - start_time} seconds")
