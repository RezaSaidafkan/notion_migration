import src.service.service_page_notion as spn
import src.repo.repo_page_notion as rpn
from src.models.client_models import ClientPage
from typing import List
import dotenv
import os
import pprint

dotenv.load_dotenv()

class Runner:
    def __init__(self):
        repo_notion = rpn.NotionClientAPI(os.getenv("NOTION_TOKEN"))
        self.service = spn.ServicePage(repo=repo_notion)

    def run(self, parent_page_id: str, database_id: str) -> List[ClientPage]:
        return self.service.get_descendants_of_parent(parent_page_id, database_id)
    
    
    
if __name__ == "__main__":
    runner = Runner()
    pages = runner.run(parent_page_id=os.getenv("SOURCE_PARENT_PAGE"), database_id=os.getenv("LIFE_STYLE_DB"))
    for page in pages:
        pprint.pprint(page)  # or any other processing
