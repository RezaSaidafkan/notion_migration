import config
import pytest


@pytest.fixture(scope="session", autouse=True)
def apply_mocked_decorators():
    config.DECORATOR_MOCK_ACTIVATED = False
    yield
