import src.service.service_page_notion as spn
import src.repo.repo_page_notion as rpn
from src.models.client_models import ClientPage
from typing import List
import dotenv
import os
import pprint
from time import time

dotenv.load_dotenv()

class Runner:
    def __init__(self):
        repo_notion = rpn.NotionClientAPI(os.getenv("NOTION_TOKEN"))
        self.service = spn.ServicePage(repo=repo_notion)

    def run(self, parent_page_id: str, source_database_id: str, journal_database_id: str, journal_db_relation: str) -> List[ClientPage]:
        root_page = self.service.get_page(parent_page_id)
        for page in self.service.build_page_hierarchy(root_page, source_database_id, journal_database_id, journal_db_relation):
            pprint.pprint(page)
        # pprint.pprint(root_page)
    
    
if __name__ == "__main__":
    start_time = time()
    runner = Runner()
    pages = runner.run(parent_page_id=os.getenv("SOURCE_PARENT_PAGE"), source_database_id=os.getenv("LIFE_STYLE_DB"), journal_database_id=os.getenv("JOURNAL_DB"), journal_db_relation=os.getenv("JOURNAL_DB_RELATION"))
    end_time = time()
    print(f"Synchronous Execution time: {end_time - start_time} seconds")
    