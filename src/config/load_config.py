from dataclasses import dataclass
import os
from dotenv import load_dotenv
from src.constants.literal_definitions import PAGINATION_SIZE

load_dotenv()

@dataclass
class Config:
    NOTION_API_KEY: str
    SOURCE_PARENT_PAGE: str
    SOURCE_DATABASE_ID: str
    JOURNAL_DATABASE_ID: str
    PAGE_SIZE: int
    SEMAPHORE_LIMIT: int
    DEBUG: bool
    
def get_config() -> Config:
    return Config(
        NOTION_API_KEY=os.getenv("NOTION_API_KEY"),
        SOURCE_PARENT_PAGE=os.getenv("SOURCE_PARENT_PAGE"),
        SOURCE_DATABASE_ID=os.getenv("SOURCE_DATABASE_ID"),
        JOURNAL_DATABASE_ID=os.getenv("TARGET_DATABASE_ID"),
        PAGE_SIZE=int(os.getenv("PAGE_SIZE", PAGINATION_SIZE)),
        SEMAPHORE_LIMIT=int(os.getenv("SEMAPHORE_LIMIT", 10)),
        DEBUG=os.getenv("DEBUG", "False").lower() in ("true", "1")
    )

class GlobalConfig:
    def __init__(self):
        if not hasattr(self, 'config'):
            self.config = get_config()

GLOBAL_CONFIG = GlobalConfig().config
