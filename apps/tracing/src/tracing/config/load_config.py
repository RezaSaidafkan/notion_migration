from common_libs.utils.load_config import get_env_vars
from pydantic import BaseModel, ValidationError

DEFAULT_TRACING_BATCH_SIZE = 20
DEFAULT_TRACING_QUEUE_SIZE = 50
DEFAULT_TRACING_DB_URI = "sqlite:///database.db"


class Config(BaseModel):
    tracing_batch_size: int
    tracing_queue_size: int
    tracing_db_uri: str


def get_vars():
    env_vars = get_env_vars()

    try:
        return Config.model_validate(
            {
            "tracing_batch_size": int(env_vars.get("TRACING_BATCH_SIZE") \
                                  or DEFAULT_TRACING_BATCH_SIZE),
            "tracing_queue_size": int(env_vars.get("TRACING_QUEUE_SIZE") \
                                  or DEFAULT_TRACING_QUEUE_SIZE),
            "tracing_db_uri": env_vars.get("TRACING_DB_URI",
                                           DEFAULT_TRACING_DB_URI)
            }
        )
    except ValidationError as e:
        raise ValueError("Failed to get proper variables") from e


TRACING_CONFIG = get_vars()
