from typing import Optional
from uuid import UUID

from common_libs.constants.literal_definitions import JunctionRelationDefinition
from common_libs.utils.load_config import get_env_vars
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
    tracing_url: str
    tracing_port: int
    notion_client_timeout_ms: float



def get_config() -> Config:
    env_vars = get_env_vars()
    try:
        return Config.model_validate(
            {
            "notion_api_key": env_vars.get("NOTION_API_KEY"),
            "source_datasource_id": env_vars.get("SOURCE_DATASOURCE_ID"),
            "journal_datasource_id": env_vars.get("JOURNAL_DATASOURCE_ID"),
            "target_datasource_id": env_vars.get("TARGET_DATASOURCE_ID"),
            "source_parent_page_id": env_vars.get("SOURCE_PARENT_PAGE_ID"),
            "junction_relation_definition": env_vars.get("JUNCTION_RELATION_DEFINITION"),
            "page_size": int(env_vars.get("PAGE_SIZE") or "1"),
            "semaphore_limit": int(env_vars.get("SEMAPHORE_LIMIT") or "10"),
            "debug": (env_vars.get("DEBUG") or "False").lower() in ("true", "1"),
            "tracing_url": env_vars.get("TRACING_URL"),
            "tracing_port": int(env_vars.get("TRACING_PORT") or "8000"),
            "notion_client_timeout_ms": float(env_vars.get("NOTION_CLIENT_TIMEOUT_MS") or 10.0),
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
