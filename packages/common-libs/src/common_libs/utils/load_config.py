import os
from typing import Dict

from dotenv import dotenv_values


def get_env_vars() -> Dict[str, str | None]:
    env_vars: Dict[str, str | None] = {
        **dotenv_values(".env"),
        **os.environ
    }
    return env_vars
