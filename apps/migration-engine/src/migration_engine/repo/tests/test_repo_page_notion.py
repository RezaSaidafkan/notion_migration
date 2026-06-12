# pylint: disable=all
import unittest
from unittest.mock import AsyncMock, patch
from uuid import UUID

from common_libs.models.api_models import ApiTaskPage
from common_libs.models.client_models import (PageId,
                                              BasePage,
                                              JournalPage, JournalProperties,
                                              TaskPage, TaskProperties,
                                              PaginationResult)
from common_libs.models.context import ExecutionContext
from common_libs.constants.literal_definitions import TaskRelationsDefinition
from migration_engine.repo.repo_page_notion import (ClientSingleton,
                                                    NotionRepoJournal,
                                                    NotionRepoSource)
from migration_engine.repo.tests.utils import create_mock_api_task_page, create_mock_api_journal_page, create_mock_api_journal_update


class TestNotionRepoTaskPage(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Reset singleton instance to ensure clean state for each test class
        ClientSingleton._instance = None
        
        # Manually start the patcher
        self.client_patcher = patch("migration_engine.repo.repo_page_notion.Client")
        mock_notion_client_class = self.client_patcher.start()

        self.mock_notion_client = AsyncMock()
        mock_notion_client_class.return_value = self.mock_notion_client
        self.repo = NotionRepoSource(notion_token="fake_token", time_out_ms=1000, debug=True)

    async def test_read_page(self):
        # Arrange
        page = BasePage(Id=PageId(Id=UUID('{12345678-1234-5678-1234-567812345678}')))
        mock_raw_page = create_mock_api_task_page(page, "Test Page")
        self.mock_notion_client.pages.retrieve.return_value = mock_raw_page.model_dump(mode="json")
        execution_id = UUID('{02345678-1234-5678-1234-567812345678}')
        execution_context = ExecutionContext(debug=True, page_size=1, execution_id=execution_id)

        result = await self.repo.read_page(page, execution_context)

        self.mock_notion_client.pages.retrieve.assert_awaited_once_with(page_id=str(page.Id.Id))
        self.assertIsInstance(result, TaskPage)
        self.assertEqual(result.Id.Id, page.Id.Id)
        self.assertEqual(result.Properties.Title.title[0].text.content, "Test Page")

    def test_convert_client_page(self):
        # Arrange
        page = BasePage(Id=PageId(Id=UUID('{12345678-1234-5678-1234-567812345678}')))
        raw_page_dict = create_mock_api_task_page(page, "Test Page")
        api_page = ApiTaskPage.model_validate(raw_page_dict)

        # Act
        client_page = self.repo.convert_client_page(api_page.model_dump(mode="json", by_alias=True, exclude_unset=True))

        # Assert
        self.assertIsInstance(client_page, TaskPage)
        self.assertEqual(client_page.Id.Id, page.Id.Id)
        self.assertIsInstance(client_page.Properties, TaskProperties)
        self.assertEqual(
            client_page.Properties.Title.title[0].text.content, "Test Page"
        )
        self.assertEqual(client_page.Properties.Type.select.name, "Task")

    async def test_query_database_single_page(self):
        # Arrange
        page = BasePage(Id=PageId(Id=UUID("12345678-1234-5678-1234-567812345678")))
        mock_response = {
            "results": [
                create_mock_api_task_page(
                    page,
                    "Page One"
                    ).model_dump(mode="json"),],
            "has_more": False,
            "next_cursor": None,
        }
        self.mock_notion_client.data_sources.query.return_value = mock_response

        db_id = UUID("22345678-1234-5678-1234-567812345678")
        execution_id = UUID('{02345678-1234-5678-1234-567812345678}')
        execution_context = ExecutionContext(debug=True, page_size=1, execution_id=execution_id)
        
        filter_query = {
             'property': 'Ancestors',
             'relation': {'contains': str(page.Id.Id)}
            }

        # Act
        result = await self.repo.query_database(
            page=page,
            data_source_id=db_id,
            relation=TaskRelationsDefinition.ANCESTORS,
            execution_context=execution_context,
            cursor=None,
        )

        # Assert
        self.mock_notion_client.data_sources.query.assert_awaited_once_with(
            str(db_id), filter=filter_query, page_size=execution_context.page_size
        )
        self.assertIsInstance(result, PaginationResult)
        self.assertFalse(result.has_more)
        self.assertIsNone(result.next_cursor)
        self.assertEqual(len(result.results), 1)
        self.assertIsInstance(result.results[0], TaskPage)
        self.assertEqual(result.results[0].Id.Id, page.Id.Id)

    async def test_query_database_paginated(self):
        """
        This test simulates pagination while the current implementation fetches
        all pages in a loop.
        """
        # Arrange
        page_1 = BasePage(Id=PageId(Id=UUID('{12345678-1234-5678-1234-567812345678}')))
        page_2 = BasePage(Id=PageId(Id=UUID('{22345678-1234-5678-1234-567812345678}')))
        page_3 = BasePage(Id=PageId(Id=UUID('{32345678-1234-5678-1234-567812345678}')))
        execution_id = UUID('{02345678-1234-5678-1234-567812345678}')
        
        mock_response_1 = {
            "results": [
                create_mock_api_task_page(
                     page_1,
                     "Page One").model_dump(mode="json"),
                create_mock_api_task_page(
                     page_2,
                     "Page Two").model_dump(mode="json"),
            ],
            "has_more": True,
            "next_cursor": "cursor123",
        }
        mock_response_2 = {
            "results": [
                create_mock_api_task_page(
                 page_3, 
                 "Page Three").model_dump(mode="json"),],
            "has_more": False,
            "next_cursor": None,
        }

        self.mock_notion_client.data_sources.query.side_effect = [
            mock_response_1,
            mock_response_2,
        ]

        db_id = UUID('{42345678-1234-5678-1234-567812345678}')
        execution_context = ExecutionContext(page_size=10, debug=True, execution_id=execution_id)

        # Act
        # The repo's query_database loops until has_more is false.
        # We expect two calls to the mock.
        result = await self.repo.query_database(
            page=page_1,
            data_source_id=db_id,
            relation=TaskRelationsDefinition.ANCESTORS,
            execution_context=execution_context,
            cursor=None)

        # Assert
        self.assertEqual(self.mock_notion_client.data_sources.query.call_count, 1)
        self.assertTrue(result.has_more)  # The final result from the repo method
        self.assertIsNotNone(
            result.next_cursor
        )  # The final result from the repo method
        self.assertEqual(len(result.results), 2)
        self.assertEqual(
            result.results[0].Id.Id,
             page_1.Id.Id)
        self.assertEqual(
            result.results[1].Id.Id,
             page_2.Id.Id)

    async def test_create_page_task(self):
        # Arrange
        # creating Mock ApiTaskPage
        base_page, page_name, _ = BasePage(Id=PageId(Id=UUID('{12345678-1234-5678-1234-567812345678}'))), "MockJournalPage", "MockJournalPageUpdated"
        mock_api_task_page = create_mock_api_task_page(base_page, page_name)
        mock_api_task_dict = mock_api_task_page.model_dump(mode="json", by_alias=True, exclude_unset=True)
        
        # creating Mock Journal Page
        mock_journal_page = self.repo.convert_client_page(mock_api_task_dict)
        
        execution_id = UUID('{02345678-1234-5678-1234-567812345678}')
        execution_context = ExecutionContext(debug=True, page_size=1, execution_id=execution_id)
        
        parent_page_id = UUID('{12345678-1234-5678-1234-567812345678}')
        
        self.mock_notion_client.pages.create.return_value = mock_api_task_dict
        
        expected_dict = mock_journal_page.model_dump(mode="json", by_alias=True, exclude={"Id"}, exclude_unset=True)
        del expected_dict["properties"]["Assignee"]
        
        # Act
        await self.repo.create_page(
            page=mock_journal_page,
            execution_context=execution_context,
            parent_page_id=parent_page_id,
        )
        
        # Assert
        self.mock_notion_client.pages.create.assert_awaited_once_with(
            parent={"data_source_id": str(parent_page_id)},
            **expected_dict
        )

    async def test_update_page(self):
        # Arrange
        base_page, page_name, updated_page_name = BasePage(Id=PageId(Id=UUID('{12345678-1234-5678-1234-567812345678}'))), "MockPage", "MockPageUpdated"
        mock_api_task_page = create_mock_api_task_page(base_page, page_name)
        mock_task_page = self.repo.convert_client_page(mock_api_task_page.model_dump(mode="json", by_alias=True, exclude_unset=True))
        
        execution_id = UUID('{02345678-1234-5678-1234-567812345678}')
        execution_context = ExecutionContext(debug=True, page_size=1, execution_id=execution_id)
        
        parent_page_id = UUID('{12345678-1234-5678-1234-567812345678}')
        
        mock_task_api_updated = create_mock_api_journal_update(base_page, updated_page_name)
        mock_task_page_updated = self.repo.convert_client_page(mock_task_api_updated.model_dump(mode="json", by_alias=True, exclude_unset=True))
        
        expected_dict = mock_task_page_updated.model_dump(mode="json", by_alias=True, exclude={"Id"}, exclude_unset=True)
        
        # Act
        await self.repo.update_target_page(
            page=mock_task_page_updated,
            execution_context=execution_context,
            parent_page_id=parent_page_id,
        )
        
        # Assert
        del expected_dict["properties"]["Assignee"]
        self.mock_notion_client.pages.update.assert_awaited_once_with(
            page_id=str(mock_task_page.Id.Id),
            **expected_dict,            
        )


    def tearDown(self):
        self.client_patcher.stop()
        

class TestNotionRepoJournalPage(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Reset singleton instance to ensure clean state for each test class
        from migration_engine.repo.repo_page_notion import ClientSingleton

        ClientSingleton._instance = None

        # Manually start the patcher
        self.client_patcher = patch("migration_engine.repo.repo_page_notion.Client")
        mock_notion_client_class = self.client_patcher.start()
        
        timeout_ms = 10000
        
        self.mock_notion_client = AsyncMock()
        mock_notion_client_class.return_value = self.mock_notion_client
        
        self.repo = NotionRepoJournal("some_api_key", timeout_ms , True)

    async def test_read_page(self):
        page = BasePage(Id=PageId(Id=UUID('{12345678-1234-5678-1234-567812345678}')))
        mock_raw_page = create_mock_api_task_page(page, "Test Journal Page")
        self.mock_notion_client.pages.retrieve.return_value = mock_raw_page.model_dump(mode="json")
        execution_id = UUID('{02345678-1234-5678-1234-567812345678}')
        execution_context = ExecutionContext(debug=True, page_size=1, execution_id=execution_id)

        result = await self.repo.read_page(page, execution_context)

        self.mock_notion_client.pages.retrieve.assert_awaited_once_with(page_id=str(page.Id.Id))
        self.assertIsInstance(result, JournalPage)
        self.assertEqual(result.Id.Id, page.Id.Id)
        self.assertEqual(
            result.Properties.Title.title[0].text.content, "Test Journal Page"
        )
        
    async def test_create_page_journal(self):
        # Arrange
        # creating Mock Journal ApiPage
        base_page, page_name, _ = BasePage(Id=PageId(Id=UUID('{12345678-1234-5678-1234-567812345678}'))), "MockJournalPage", "MockJournalPageUpdated"
        mock_api_journal_page = create_mock_api_journal_page(base_page, page_name)
        mock_api_journal_dict = mock_api_journal_page.model_dump(mode="json", by_alias=True, exclude_unset=True)
        
        # creating Mock Journal Page
        mock_journal_page = self.repo.convert_client_page(mock_api_journal_dict)
        
        execution_id = UUID('{02345678-1234-5678-1234-567812345678}')
        execution_context = ExecutionContext(debug=True, page_size=1, execution_id=execution_id)
        
        parent_page_id = UUID('{12345678-1234-5678-1234-567812345678}')
        
        self.mock_notion_client.pages.create.return_value = mock_api_journal_dict
        
        expected_dict = mock_journal_page.model_dump(mode="json", by_alias=True, exclude={"Id"}, exclude_unset=True)
        
        # Act
        await self.repo.create_page(
            page=mock_journal_page,
            execution_context=execution_context,
            parent_page_id=parent_page_id,
        )
        
        # Assert
        self.mock_notion_client.pages.create.assert_awaited_once_with(
            parent={"data_source_id": str(parent_page_id)},
            **expected_dict
        )

    def test_convert_client_page(self):
        page = BasePage(Id=PageId(Id=UUID('{12345678-1234-5678-1234-567812345678}')))
        api_journal_page = create_mock_api_journal_page(page, "Test Journal Page")
        api_journal_page_dict = api_journal_page.model_dump(mode="jsone")

        client_page = self.repo.convert_client_page(api_journal_page_dict)

        self.assertIsInstance(client_page, JournalPage)
        self.assertEqual(client_page.Id.Id, page.Id.Id)
        self.assertIsInstance(client_page.Properties, JournalProperties)
        self.assertEqual(
            client_page.Properties.Title.title[0].text.content, "Test Journal Page"
        )
        self.assertEqual(client_page.Properties.Type.select.name, "Task")
        # JournalPageProperties doesn't have Assignee, Priority, etc.
        self.assertFalse(hasattr(client_page.Properties, "Assignee"))

    def tearDown(self):
        self.client_patcher.stop()


if __name__ == "__main__":
    unittest.main()
