import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from src.repo.repo_page_notion import NotionRepoPage, NotionRepoJournalPage
from src.models.client_models import Page, JournalPage, PageId, PageProperties, JournalPageProperties, PaginationResult
from src.models.api_models import ApiPage


def create_mock_api_page(page_id: str, title: str) -> dict:
    """Helper function to create a mock raw API page dictionary."""
    return {
        "object": "page",
        "id": page_id,
        "created_time": "2022-01-01T00:00:00.000Z",
        "last_edited_time": "2022-01-01T00:00:00.000Z",
        "parent": {"type": "data_source_id", "data_source_id": "db_id"},
        "archived": False,
        "icon": None,
        "properties": {
            "Title": {
                "id": "title",
                "type": "title",
                "title": [{"type": "text", "text": {"content": title, "link": None}, "plain_text": title}]
            },
            "Type": {
                "id": "type_id",
                "type": "select",
                "select": {"id": "select_id", "name": "Task", "color": "blue"}
            },
            "Status": {
                "id": "status_id",
                "type": "status",
                "status": {"id": "status_opt_id", "name": "In Progress", "color": "yellow"}
            },
            "Timeline": {
                "id": "date_id",
                "type": "date",
                "date": {"start": "2023-01-01", "end": None, "time_zone": None}
            },
            "Assignee": None,
            "Priority": None,
            "Urgency": None,
            "Description": None,
            "Ancestors": None,
            "Descendants": None,
            "Journals": None,
        }
    }


class TestNotionRepoPage(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Reset singleton instance to ensure clean state for each test class
        from src.repo.repo_page_notion import ClientSingleton
        ClientSingleton._instance = None

        # Manually start the patcher
        self.client_patcher = patch('src.repo.repo_page_notion.Client')
        mock_notion_client_class = self.client_patcher.start()

        self.mock_notion_client = AsyncMock()
        mock_notion_client_class.return_value = self.mock_notion_client
        self.repo = NotionRepoPage(notion_token="fake_token")

    async def test_read_page(self):
        page_id = "test-page-id"
        mock_raw_page = create_mock_api_page(page_id, "Test Page")
        self.mock_notion_client.pages.retrieve.return_value = mock_raw_page

        result = await self.repo.read_page(PageId(Id=page_id))

        self.mock_notion_client.pages.retrieve.assert_awaited_once_with(page_id=page_id)
        self.assertIsInstance(result, Page)
        self.assertEqual(result.Id.Id, page_id)
        self.assertEqual(result.Properties.Title.title[0].text.content, "Test Page")

    def test_convert_client_page(self):
        # Arrange
        page_id = "test-page-id"
        raw_page_dict = create_mock_api_page(page_id, "Test Page")
        api_page = ApiPage.model_validate(raw_page_dict)
        
        # Act
        client_page = self.repo.convert_client_page(api_page)

        # Assert
        self.assertIsInstance(client_page, Page)
        self.assertEqual(client_page.Id.Id, page_id)
        self.assertIsInstance(client_page.Properties, PageProperties)
        self.assertEqual(client_page.Properties.Title.title[0].text.content, "Test Page")
        self.assertEqual(client_page.Properties.Type.select.name, "Task")

    async def test_query_database_single_page(self):
        # Arrange
        mock_response = {
            "results": [create_mock_api_page("page1", "Page One")],
            "has_more": False,
            "next_cursor": None,
        }
        self.mock_notion_client.data_sources.query.return_value = mock_response

        db_id = "test-db-id"
        page_size = 10
        filter_dict = {"property": "Status", "status": {"equals": "In Progress"}}

        # Act
        result = await self.repo.query_database(
            data_source_id=db_id,
            page_size=page_size,
            filter_query=filter_dict,
            cursor=None
        )

        # Assert
        self.mock_notion_client.data_sources.query.assert_awaited_once_with(
            db_id, start_cursor=None, filter=filter_dict, page_size=page_size
        )
        self.assertIsInstance(result, PaginationResult)
        self.assertFalse(result.has_more)
        self.assertIsNone(result.next_cursor)
        self.assertEqual(len(result.results), 1)
        self.assertIsInstance(result.results[0], Page)
        self.assertEqual(result.results[0].Id.Id, "page1")

    async def test_query_database_paginated(self):
        ''' This test simulates pagination while the current implementation fetches all pages in a loop. '''
        
        # Arrange
        mock_response_1 = {
            "results": [create_mock_api_page("page1", "Page One"),
                        create_mock_api_page("page2", "Page Two"), ],
            "has_more": True,
            "next_cursor": "cursor123",
        }
        mock_response_2 = {
            "results": [create_mock_api_page("page3", "Page Three")],
            "has_more": False,
            "next_cursor": None,
        }
        
        self.mock_notion_client.data_sources.query.side_effect = [mock_response_1, mock_response_2]

        db_id = "test-db-id"
        page_size = 2

        # The repo's query_database loops until has_more is false.
        # We expect two calls to the mock.
        result = await self.repo.query_database(
            data_source_id=db_id,
            page_size=page_size,
            filter_query={},
            cursor=None
        )

        self.assertEqual(self.mock_notion_client.data_sources.query.call_count, 1)
        self.assertTrue(result.has_more) # The final result from the repo method
        self.assertIsNotNone(result.next_cursor) # The final result from the repo method
        self.assertEqual(len(result.results), 2)
        self.assertEqual(result.results[0].Id.Id, "page1")
        self.assertEqual(result.results[1].Id.Id, "page2")

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
        from src.repo.repo_page_notion import ClientSingleton
        ClientSingleton._instance = None

        # Manually start the patcher
        self.client_patcher = patch('src.repo.repo_page_notion.Client')
        mock_notion_client_class = self.client_patcher.start()

        self.mock_notion_client = AsyncMock()
        mock_notion_client_class.return_value = self.mock_notion_client
        self.repo = NotionRepoJournalPage(notion_token="fake_token")

    async def test_read_page(self):
        page_id = "test-journal-page-id"
        mock_raw_page = create_mock_api_page(page_id, "Test Journal Page")
        self.mock_notion_client.pages.retrieve.return_value = mock_raw_page

        result = await self.repo.read_page(PageId(Id=page_id))

        self.mock_notion_client.pages.retrieve.assert_awaited_once_with(page_id=page_id)
        self.assertIsInstance(result, JournalPage)
        self.assertEqual(result.Id.Id, page_id)
        self.assertEqual(result.Properties.Title.title[0].text.content, "Test Journal Page")

    def test_convert_client_page(self):
        page_id = "test-journal-page-id"
        raw_page_dict = create_mock_api_page(page_id, "Test Journal Page")
        api_page = ApiPage.model_validate(raw_page_dict)

        client_page = self.repo.convert_client_page(api_page)

        self.assertIsInstance(client_page, JournalPage)
        self.assertEqual(client_page.Id.Id, page_id)
        self.assertIsInstance(client_page.Properties, JournalPageProperties)
        self.assertEqual(client_page.Properties.Title.title[0].text.content, "Test Journal Page")
        self.assertEqual(client_page.Properties.Type.select.name, "Task")
        # JournalPageProperties doesn't have Assignee, Priority, etc.
        self.assertFalse(hasattr(client_page.Properties, 'Assignee'))

    def tearDown(self):
        self.client_patcher.stop()


if __name__ == '__main__':
    unittest.main()