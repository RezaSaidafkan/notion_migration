# pylint: disable=all
import os
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4
from common_libs.models.client_models import JunctionRelationDefinition

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
    "tracing_url": "some/url",
    "tracing_port": "1234",
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


class TestTracing(unittest.IsolatedAsyncioTestCase):
    @patch.dict(os.environ, env_vars_for_test)
    @patch("migration_engine.main.NotionRepoSource")
    @patch("migration_engine.main.NotionRepoJournal")
    @patch("migration_engine.repo.repo_page_notion.NotionRepoSource")
    @patch("migration_engine.repo.repo_page_notion.NotionRepoJournal")
    async def test_tracing_on_exception(
        self,
        mocked_notion_repo_journal_def: MagicMock,
        mocked_notion_repo_source_def: MagicMock,
        mocked_notion_repo_journal: MagicMock,
        mocked_notion_repo_source: MagicMock):
        # Arrange

        with patch("common_libs.utils.tracing.Tracing") as mocked_tracing,\
            patch("migration_engine.repo.repo_page_notion.retry"),\
            patch("migration_engine.repo.repo_page_notion.rate_limited"):
            from migration_engine.repo.repo_page_interface import RepositoryError
            
            # Setup the mock instances that will be returned when the classes are instantiated
            
            mock_source_instance = AsyncMock()
            mock_source_instance.read_page = AsyncMock(side_effect=[RepositoryError(message="Mocked read_page Error")] * 4)
            mock_source_instance.query_database = AsyncMock(side_effect=[RepositoryError(message="Mocked query_database Error")] * 4)
            mocked_notion_repo_source.return_value = mock_source_instance
            mocked_notion_repo_source_def.return_value = mock_source_instance
            
            mock_journal_instance = AsyncMock()
            mock_journal_instance.read_page = AsyncMock(side_effect=[RepositoryError(message="Mocked read_page Error")] * 4)
            mock_journal_instance.query_database = AsyncMock(side_effect=[RepositoryError(message="Mocked query_database Error")] * 4)
            mocked_notion_repo_journal.return_value = mock_journal_instance
            mocked_notion_repo_journal_def.return_value = mock_journal_instance

            mocked_tracing_singleton = MagicMock(name="mocked_tracing_singleton")
            mocked_tracing.return_value = mocked_tracing_singleton
            mocked_send_trace_page = MagicMock(name="send_trace_page")
            mocked_tracing_singleton.send_trace_page = mocked_send_trace_page
            
            # Act & Assert
            from migration_engine.main import execute_migration_engine, MigrationEngineError
            with self.assertRaises(MigrationEngineError):
                await execute_migration_engine()
            mocked_tracing.return_value.send_trace_page.assert_called_once()
            assert "Mocked read_page Error" in str(mocked_tracing.return_value.send_trace_page.mock_calls[0])

    def tearDown(self):
        pass

if __name__ == "__main__":
    unittest.main()
