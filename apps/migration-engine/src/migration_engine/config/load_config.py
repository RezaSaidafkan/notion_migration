import os
from dataclasses import dataclass

from dotenv import dotenv_values


# pylint: disable = too-many-instance-attributes
@dataclass
class Config:
    notion_api_key: str | None
    source_parent_page: str | None
    source_database_id_life_style: str | None
    source_database_id_nucleus: str | None
    journal_database_id: str | None
    pagination_size: int
    semaphore_limit: int
    debug: bool


def get_config() -> Config:
    env_vars = {
        **dotenv_values(".env"),
        **os.environ
    }
    return Config(
        notion_api_key=env_vars.get("NOTION_API_KEY") or None,
        source_parent_page=env_vars.get("SOURCE_PARENT_PAGE") or None,
        source_database_id_life_style=env_vars.get("SOURCE_DATABASE_ID_LIFE_STYLE") or None,
        source_database_id_nucleus=env_vars.get("SOURCE_DATABASE_ID_NUCLEUS") or None,
        journal_database_id=env_vars.get("TARGET_DATABASE_ID") or None,
        pagination_size=int(env_vars.get("PAGINATION_SIZE") or "1"),
        semaphore_limit=int(env_vars.get("SEMAPHORE_LIMIT") or "10"),
        debug=(env_vars.get("DEBUG") or "False").lower() in ("true", "1"),
    )


# pylint: disable = too-few-public-methods
class GlobalConfig:
    config: Config
    singleton = False

    def __init__(self):
        if not self.singleton:
            self.config = get_config()
            self.singleton = True


GLOBAL_CONFIG = GlobalConfig().config
