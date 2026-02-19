import os
from typing import Optional
from uuid import UUID

from common_libs.constants.literal_definitions import JunctionRelationDefinition
from dotenv import dotenv_values
from pydantic import UUID4, BaseModel, ValidationError


# pylint: disable = too-many-instance-attributes
class Config(BaseModel):
    notion_api_key: str
    source_datasource_id: UUID4
    journal_datasource_id: UUID4
    target_datasource_id: Optional[UUID4]
    source_parent_page_id: UUID
    junction_relation_definition: JunctionRelationDefinition
    page_size: int
    semaphore_limit: int
    debug: bool


def get_config() -> Config:
    env_vars = {
        **dotenv_values(".env"),
        **os.environ
    }
    try:
        return Config.model_validate(
            {
            "notion_api_key": env_vars.get("NOTION_API_KEY") or None,
            "source_datasource_id": env_vars.get("SOURCE_DATASOURCE_ID") or None,
            "journal_datasource_id": env_vars.get("JOURNAL_DATASOURCE_ID") or None,
            "target_datasource_id": env_vars.get("TARGET_DATASOURCE_ID") or None,
            "source_parent_page_id": env_vars.get("SOURCE_PARENT_PAGE_ID") or None,
            "junction_relation_definition": env_vars.get("JUNCTION_RELATION_DEFINITION") or None,
            "page_size": int(env_vars.get("PAGE_SIZE") or "1"),
            "semaphore_limit": int(env_vars.get("SEMAPHORE_LIMIT") or "10"),
            "debug": (env_vars.get("DEBUG") or "False").lower() in ("true", "1")
            }
        )
    except ValidationError as e:
        raise ValueError("Failed to get proper variables") from e


# pylint: disable = too-few-public-methods
class GlobalConfig:
    config: Config
    singleton = False

    def __init__(self):
        if not self.singleton:
            self.config = get_config()
            self.singleton = True


GLOBAL_CONFIG = GlobalConfig().config
