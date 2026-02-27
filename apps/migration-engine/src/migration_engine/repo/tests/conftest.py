import pytest
import config


@pytest.fixture(scope="session", autouse=True)
def apply_mocked_decorators():
    config.decorator_mock_activated = True
    print("zzzzz decorator_mock_activated", config.decorator_mock_activated)
    yield
