import os
from dataclasses import dataclass

from dotenv import load_dotenv

from src.constants.literal_definitions import PAGINATION_SIZE

load_dotenv()


# pylint: disable = too-many-instance-attributes
@dataclass
class Config:
    notion_api_key: str | None
    source_parent_page: str | None
    source_database_id_life_style: str | None
    source_database_id_nucleus: str | None
    journal_database_id: str | None
    page_size: int
    semaphore_limit: int
    debug: bool


def get_config() -> Config:
    return Config(
        notion_api_key=os.getenv("NOTION_API_KEY"),
        source_parent_page=os.getenv("SOURCE_PARENT_PAGE"),
        source_database_id_life_style=os.getenv("SOURCE_DATABASE_ID_LIFE_STYLE"),
        source_database_id_nucleus=os.getenv("SOURCE_DATABASE_ID_NUCLEUS"),
        journal_database_id=os.getenv("TARGET_DATABASE_ID"),
        page_size=int(os.getenv("PAGE_SIZE", str(PAGINATION_SIZE))),
        semaphore_limit=int(os.getenv("SEMAPHORE_LIMIT", "10")),
        debug=os.getenv("DEBUG", "False").lower() in ("true", "1"),
    )


# pylint: disable = too-few-public-methods
class GlobalConfig:
    config: Config = None

    def __init__(self):
        if self.config is None:
            self.config = get_config()


GLOBAL_CONFIG = GlobalConfig().config
