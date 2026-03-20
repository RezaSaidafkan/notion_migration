# pylint: disable=all
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID
from typing import Dict, Any
import pytest

from common_libs.models.api_models import ApiPage
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


def create_mock_api_page(page: BasePage, title: str) -> Dict[str, Any]:
    """Helper function to create a mock raw API page dictionary."""
    return {
        "object": "page",
        "id": page.Id.Id,
        "created_time": "2022-01-01T00:00:00.000Z",
        "last_edited_time": "2022-01-01T00:00:00.000Z",
        "parent": {"type": "data_source_id", "data_source_id": "db_id"},
        "archived": False,
        "icon": None,
        "properties": {
            "Title": {
                "id": "title_id",
                "type": "title",
                "title": [
                    {
                        "type": "text",
                        "text": {"content": title, "link": None},
                        "plain_text": title,
                    }
                ],
            },
            "Type": {
                "id": "type_id",
                "type": "select",
                "select": {"id": "select_id", "name": "Task", "color": "blue"},
            },
            "Status": {
                "id": "status_id",
                "type": "status",
                "status": {
                    "id": "status_opt_id",
                    "name": "In Progress",
                    "color": "yellow",
                },
            },
            "Timeline": {
                "id": "date_id",
                "type": "date",
                "date": {"start": "2023-01-01", "end": None, "time_zone": None},
            },
            "Assignee": None,
            "Priority": None,
            "Urgency": None,
            "Description": None,
            "Ancestors": None,
            "Descendants": None,
            "Journals": None,
        },
    }


class TestNotionRepoPage(unittest.IsolatedAsyncioTestCase):
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
        page = BasePage(Id=PageId(Id=UUID('{12345678-1234-5678-1234-567812345678}')))
        mock_raw_page = create_mock_api_page(page, "Test Page")
        self.mock_notion_client.pages.retrieve.return_value = mock_raw_page

        result = await self.repo.read_page(page)

        self.mock_notion_client.pages.retrieve.assert_awaited_once_with(page_id=str(page.Id.Id))
        self.assertIsInstance(result, TaskPage)
        self.assertEqual(result.Id.Id, page.Id.Id)
        self.assertEqual(result.Properties.Title.title[0].text.content, "Test Page")

    def test_convert_client_page(self):
        # Arrange
        page = BasePage(Id=PageId(Id=UUID('{12345678-1234-5678-1234-567812345678}')))
        raw_page_dict = create_mock_api_page(page, "Test Page")
        api_page = ApiPage.model_validate(raw_page_dict)

        # Act
        client_page = self.repo.convert_client_page(api_page)

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
                create_mock_api_page(
                    page,
                    "Page One"
                    )],
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
            str(db_id), start_cursor=None, filter=filter_query, page_size=execution_context.page_size
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
                create_mock_api_page(
                     page_1,
                     "Page One"),
                create_mock_api_page(
                     page_2,
                     "Page Two"),
            ],
            "has_more": True,
            "next_cursor": "cursor123",
        }
        mock_response_2 = {
            "results": [
                create_mock_api_page(
                 page_3, 
                 "Page Three")],
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

    async def test_create_page_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            await self.repo.create_page(MagicMock(), debug=False)

    async def test_update_page_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            await self.repo.update_page(MagicMock(), debug=False)

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
        mock_raw_page = create_mock_api_page(page, "Test Journal Page")
        self.mock_notion_client.pages.retrieve.return_value = mock_raw_page

        result = await self.repo.read_page(page)

        self.mock_notion_client.pages.retrieve.assert_awaited_once_with(page_id=str(page.Id.Id))
        self.assertIsInstance(result, JournalPage)
        self.assertEqual(result.Id.Id, page.Id.Id)
        self.assertEqual(
            result.Properties.Title.title[0].text.content, "Test Journal Page"
        )

    def test_convert_client_page(self):
        page = BasePage(Id=PageId(Id=UUID('{12345678-1234-5678-1234-567812345678}')))
        raw_page_dict = create_mock_api_page(page, "Test Journal Page")
        api_page = ApiPage.model_validate(raw_page_dict)

        client_page = self.repo.convert_client_page(api_page)

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
