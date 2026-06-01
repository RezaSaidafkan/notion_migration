import logging.config
from typing import Any, Dict, Optional

import httpx

from common_libs.models.tracing_models import TracePage

LOGGING_CONFIG: Dict[Any, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "http",
            "stream": "ext://sys.stderr"
        }
    },
    "formatters": {
        "http": {
            "format": "%(levelname)s [%(asctime)s] %(name)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    'loggers': {
        'httpx': {
            'handlers': ['default'],
            'level': 'WARNING',
        },
        'httpcore': {
            'handlers': ['default'],
            'level': 'WARNING',
        },
    }
}

logging.config.dictConfig(LOGGING_CONFIG)


class TracingException(Exception):
    pass


class Singleton(type):
    instances: Dict[Singleton, Any] = {}

    def __call__(cls, *args: Any, **kwds: Any) -> Any:
        if not cls.instances:
            instance = super().__call__(*args, **kwds)
            cls.instances[cls] = instance
        return cls.instances[cls]

# pylint: disable=too-few-public-methods
class Tracing(metaclass=Singleton):
    def __init__(self, address: Optional[str]=None, port: Optional[int]=None) -> None:
        self._address = address
        self._port = port
        self._url = f"http://{self._address}:{self._port}"

    def send_trace_page(self, body: TracePage):
        try:
            with httpx.Client() as client:
                response = client.post(f"{self._url}/trace_page", json=body.model_dump(mode="json"))
                response.raise_for_status()
        except httpx.HTTPError as t_e:
            raise TracingException(
                f"Failed to send tracing for:\t{body.page_id.Id}\t{body.trace.function_name}",
                ) from t_e
        except Exception as e:
            raise TracingException(
                f"Unknown issue is sending tracing for:\t\
                {body.page_id.Id}\t{body.trace.function_name}",
                ) from e
