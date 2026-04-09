from uuid import UUID

from common_libs.constants.literal_definitions import JunctionRelationDefinition
from common_libs.utils.load_config import get_env_vars
from pydantic import UUID4, BaseModel, ValidationError

DEFAULT_TIME_PERIOD = 1
DEFAULT_MAX_RATE = 3
DEFAULT_NOTION_CLIENT_TIMEOUT_MS = 10
DEFAULT_SEMAPHORE_LIMIT = 10
DEFAULT_PAGE_SIZE = 1
DEFFAULT_TRACING_PORT = 8000
DEFAULT_TIMEOUT_RETRY = 5

# pylint: disable = too-many-instance-attributes
class Config(BaseModel):
    notion_api_key: str
    source_datasource_id: UUID4
    journal_datasource_id: UUID4
    target_datasource_id: UUID4
    source_parent_page_id: UUID
    junction_relation_definition: JunctionRelationDefinition
    page_size: int
    semaphore_limit: int
    debug: bool
    tracing_url: str
    tracing_port: int
    notion_client_timeout_ms: float
    time_period: int
    max_rate: int
    timeout_retry: int


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
            "page_size": int(env_vars.get("PAGE_SIZE") or DEFAULT_PAGE_SIZE),
            "semaphore_limit": int(env_vars.get("SEMAPHORE_LIMIT") or DEFAULT_SEMAPHORE_LIMIT),
            "debug": (env_vars.get("DEBUG") or "False").lower() in ("true", "1"),
            "tracing_url": env_vars.get("TRACING_URL"),
            "tracing_port": int(env_vars.get("TRACING_PORT") or DEFFAULT_TRACING_PORT),
            "notion_client_timeout_ms":
                float(env_vars.get("NOTION_CLIENT_TIMEOUT_MS") or DEFAULT_NOTION_CLIENT_TIMEOUT_MS),
            "time_period": int(env_vars.get("TIME_PERIOD") or DEFAULT_TIME_PERIOD),
            "max_rate": int(env_vars.get("MAX_RATE") or DEFAULT_MAX_RATE),
            "timeout_retry": int(env_vars.get("TIMEOUT_RETRY") or DEFAULT_TIMEOUT_RETRY)

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
