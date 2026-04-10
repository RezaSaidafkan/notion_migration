import json
import os
import unittest
from functools import reduce
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from common_libs.models.client_models import JunctionRelationDefinition
from httpx import Response
from notion_client.errors import APIErrorCode, APIResponseError, RequestTimeoutError

tests_dir_path = Path().cwd().joinpath(
    "apps/migration-engine/src/migration_engine/repo/tests/tests_decorated/")
response_root_file_path = tests_dir_path.joinpath("response_root.json")


config = {
    "notion_api_key": "some key",
    "source_datasource_id": str(uuid4()),
    "journal_datasource_id": str(uuid4()),
    "target_datasource_id": str(uuid4()),
    "source_parent_page_id": str(uuid4()),
    "junction_relation_definition": JunctionRelationDefinition.LIFE_STYLE.value,
    "page_size": "10",
    "semaphore_limit": "10",
    "debug": "True",
    "tracing_url": "127.0.0.1", # "some/url",
    "tracing_port": "8000", #"1234",
    "notion_client_timeout_ms": "50.0"
    }

# Required environment variables for config loading
env_vars_for_test = {
    "NOTION_API_KEY": config["notion_api_key"],
    "SOURCE_DATASOURCE_ID": config["source_datasource_id"],
    "JOURNAL_DATASOURCE_ID": config["journal_datasource_id"],
    "TARGET_DATASOURCE_ID": config["target_datasource_id"],
    "SOURCE_PARENT_PAGE_ID": config["source_parent_page_id"],
    "JUNCTION_RELATION_DEFINITION": config["junction_relation_definition"],
    "PAGE_SIZE": config["page_size"],
    "SEMAPHORE_LIMIT": config["semaphore_limit"],
    "DEBUG": config["debug"],
    "TRACING_URL": config["tracing_url"],
    "TRACING_PORT": config["tracing_port"],
    "NOTION_CLIENT_TIMEOUT_MS": config["notion_client_timeout_ms"]
}


class TestRetries(unittest.IsolatedAsyncioTestCase):
    @patch.dict(os.environ, env_vars_for_test)
    @patch("migration_engine.repo.repo_page_notion.Client")
    async def test_retry_rate_limited_api_response_error(self, mocked_async_client: MagicMock):
        # Arrange
        # mocking await self.notion.data_sources.query(data_source_id, **query)
        ## mocking erroneous responses
        mocked_response = AsyncMock(
                name="mocked_response",
                spec=Response)
        mocked_response.headers = {"Retry-After": 0.01}
        mocked_response.status_code = 429
        errors_list = [
                APIResponseError(
                code=APIErrorCode.RateLimited,
                message=f"msg {i} APIResponseError",
                response=mocked_response) for i in range(6)
                ]

        mocked_async_client_instance = mocked_async_client.return_value
        mocked_async_client_instance.data_sources.query = AsyncMock(
            name="async_mocked_query",
            side_effect=errors_list)

        with open(response_root_file_path, "rb") as retrieve_file:
            response_root = json.load(retrieve_file)

        mocked_async_client_instance.pages.retrieve = AsyncMock(
            name="mocked_retrieve",
            return_value = response_root)

        with patch("common_libs.utils.tracing.Tracing") as mocked_tracing,\
            patch("migration_engine.repo.repo_page_notion.RETRY_TIMEOUT_FALLBACK", 0.01),\
            patch("common_libs.singletons.rate_limiter_singleton.AsyncLimiter"):
            from migration_engine.main import execute_migration_engine

            tracing_instance = mocked_tracing.return_value

            # Act
            await execute_migration_engine()

            # Assert
            path = ["trace", "outcome", "failure"]
            results = [
                reduce(lambda d, key: d.get(key, {}) if isinstance(d, dict) else None,
                       path, call.args[0].model_dump())
                for call in tracing_instance.send_trace_page.call_args_list]

            api_response_error_exceptions = [
                d.get("exception_value") for d in results
                if d is not None and d.get("exception_type", "") == "APIResponseError"]
            assert set(api_response_error_exceptions) == set(f"msg {i} APIResponseError" for i in range(3))

    @patch.dict(os.environ, env_vars_for_test)
    @patch("migration_engine.repo.repo_page_notion.Client")
    async def test_retry_rate_limited_request_timeout_error(self, mocked_async_client: MagicMock):
        # Arrange
        # mocking await self.notion.data_sources.query(data_source_id, **query)
        ## mocking erroneous responses
        errors_list = [
                RequestTimeoutError(
                message=f"msg {i} RequestTimeoutError") for i in range(6)
                ]

        mocked_async_client_instance = mocked_async_client.return_value
        mocked_async_client_instance.data_sources.query = AsyncMock(
            name="async_mocked_query",
            side_effect=errors_list)

        with open(response_root_file_path, "rb") as retrieve_file:
            response_root = json.load(retrieve_file)

        # mocking await self.notion.pages.retrieve(data_source_id)
        mocked_async_client_instance.pages.retrieve = AsyncMock(
            name="mocked_retrieve",
            return_value = response_root)

        with patch("common_libs.utils.tracing.Tracing") as mocked_tracing,\
            patch("migration_engine.repo.repo_page_notion.RETRY_TIMEOUT_FALLBACK", 0.01),\
            patch("common_libs.singletons.rate_limiter_singleton.AsyncLimiter"):
            from migration_engine.main import execute_migration_engine

            tracing_instance = mocked_tracing.return_value

            # Act & Assert
            await execute_migration_engine()
            path = ["trace", "outcome", "failure"]
            results = [
                reduce(lambda d, key: d.get(key, {}) if isinstance(d, dict) else None,
                       path, call.args[0].model_dump())
                for call in tracing_instance.send_trace_page.call_args_list]
            api_response_error_exceptions = [
                d.get("exception_value") for d in results
                if d is not None and d.get("exception_type", "") == "RequestTimeoutError"]
            assert set(api_response_error_exceptions) == set(f"msg {i} RequestTimeoutError" for i in range(3))


    @patch.dict(os.environ, env_vars_for_test)
    @patch("migration_engine.repo.repo_page_notion.Client")
    async def test_retry_both_errors(self, mocked_async_client: MagicMock):
        # Arrange
        # mocking await self.notion.data_sources.query(data_source_id, **query)
        ## mocking erroneous responses

        mocked_response = AsyncMock(
                name="mocked_response",
                spec=Response)
        mocked_response.headers = {"Retry-After": 0.01}
        mocked_response.status_code = 429
        errors_list = [
                APIResponseError(
                    code=APIErrorCode.RateLimited,
                    message=f"msg {i} APIResponseError",
                    response=mocked_response) for i in range(3)
                ] + [
                RequestTimeoutError(
                    message=f"msg {i} RequestTimeoutError") for i in range(4)
                ]

        mocked_async_client_instance = mocked_async_client.return_value
        mocked_async_client_instance.data_sources.query = AsyncMock(
            name="async_mocked_query",
            side_effect=errors_list)

        # mocking RETRY_TIMEOUT_FALLBACK

        with open(response_root_file_path, "rb") as retrieve_file:
            response_root = json.load(retrieve_file)

        # mocking await self.notion.pages.retrieve(data_source_id)
        mocked_async_client_instance.pages.retrieve = AsyncMock(
            name="mocked_retrieve",
            return_value = response_root)

        with patch("common_libs.utils.tracing.Tracing") as mocked_tracing,\
            patch("common_libs.singletons.rate_limiter_singleton.AsyncLimiter"),\
            patch("migration_engine.repo.repo_page_notion.RETRY_TIMEOUT_FALLBACK", 0.01):
            from migration_engine.main import MigrationEngineError, execute_migration_engine
                
            tracing_instance = mocked_tracing.return_value

            # Act & Assert
            await execute_migration_engine()
            path = ["trace", "outcome", "failure"]
            results = [
                reduce(lambda d, key: d.get(key, {}) if isinstance(d, dict) else None,
                       path, call.args[0].model_dump())
                for call in tracing_instance.send_trace_page.call_args_list]
            
            both_exceptions = [
                d.get("exception_value") for d in results
                if d is not None and d.get("exception_type", "") in ["RequestTimeoutError", "APIResponseError"]]
            assert set(both_exceptions) == set(f"msg {i} RequestTimeoutError" for i in range(3)).union(set(f"msg {i} APIResponseError" for i in range(3)))


if __name__ == "__main__":
    unittest.main()
