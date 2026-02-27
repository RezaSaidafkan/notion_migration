import pytest
import config


@pytest.fixture(scope="session", autouse=True)
def apply_mocked_decorators():
    config.decorator_mock_activated = False
    yield


