# pylint: disable=all
import unittest
from unittest.mock import AsyncMock, call, patch

from src.constants.literal_definitions import DatabaseInfo, JournalRelations
from src.models.api_models import TitleItem, TitleProperty, TitleText
from src.models.client_models import (
    JournalPage,
    JournalPageProperties,
    Page,
    PageId,
    PageProperties,
    PaginationResult,
)
from src.service.service_page_notion import ServicePage


def create_mock_page(
    page_id: str, title: str, model: type[Page] | type[JournalPage] = Page
) -> Page | JournalPage:
    """Helper to create a mock Page or JournalPage."""
    mock_title = TitleProperty(
        id="title_id",
        type="title",
        title=[TitleItem(type="text", text=TitleText(content=title, link=None))],
    )
    properties: PageProperties | JournalPageProperties
    if model == Page:
        properties = PageProperties(
            Title=mock_title,
            Type=None,
            Assignee=None,
            Priority=None,
            Urgency=None,
            Status=None,
            Timeline=None,
            Description=None,
        )
    else:
        properties = JournalPageProperties(
            Title=mock_title,
            Type=None,
            Status=None,
            Timeline=None,
            Description=None,
        )
    return model(Id=PageId(Id=page_id), Icon=None, Properties=properties)


class TestServicePage(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_repo_source = AsyncMock()
        self.mock_repo_journal = AsyncMock()
        self.service = ServicePage(
            repo_source=self.mock_repo_source, repo_journal=self.mock_repo_journal
        )

    async def test_refresh_from_backend(self):
        """Test that refresh_from_backend calls the source repo and returns a Page."""
        # Arrange
        page_id = PageId(Id="test-page-id")
        mock_page = create_mock_page(page_id.Id, "Test Page")
        self.mock_repo_source.read_page.return_value = mock_page

        # Act
        result = await self.service.read_page(page_id)

        # Assert
        self.mock_repo_source.read_page.assert_awaited_once_with(page_id)
        self.assertIsInstance(result, Page)
        self.assertEqual(result.Id, page_id)
        self.assertEqual(result.Properties.Title, mock_page.Properties.Title)

    async def test_query_database_for_source_pages(self):
        """Test querying for Page types uses the source repo."""
        db_info = DatabaseInfo(DatabaseId="source-db")
        mock_pages = [create_mock_page("p1", "Page 1")]
        self.mock_repo_source.query_database.return_value = PaginationResult(
            results=mock_pages, has_more=False, next_cursor=None
        )

        result = await self.service.query_database(
            database_info=db_info, database_type=Page, filter_query={}
        )

        self.mock_repo_source.query_database.assert_awaited_once()
        self.mock_repo_journal.query_database.assert_not_awaited()
        self.assertEqual(result, mock_pages)

    async def test_query_database_for_journal_pages(self):
        """Test querying for JournalPage types uses the journal repo."""
        db_info = DatabaseInfo(DatabaseId="journal-db")
        mock_journal_pages = [create_mock_page("j1", "Journal 1", model=JournalPage)]
        self.mock_repo_journal.query_database.return_value = PaginationResult(
            results=mock_journal_pages, has_more=False, next_cursor=None
        )

        result = await self.service.query_database(
            database_info=db_info, database_type=JournalPage, filter_query={}
        )

        self.mock_repo_journal.query_database.assert_awaited_once()
        self.mock_repo_source.query_database.assert_not_awaited()
        self.assertEqual(result, mock_journal_pages)

    async def test_query_database_with_pagination(self):
        """Test that query_database handles pagination correctly."""
        # Arrange
        db_info = DatabaseInfo(DatabaseId="source-db")
        mock_page1 = create_mock_page("p1", "Page 1")
        mock_page2 = create_mock_page("p2", "Page 2")

        self.mock_repo_source.query_database.side_effect = [
            PaginationResult(
                results=[mock_page1], has_more=True, next_cursor="cursor1"
            ),
            PaginationResult(results=[mock_page2], has_more=False, next_cursor=None),
        ]

        # Act
        result = await self.service.query_database(
            database_info=db_info, database_type=Page, filter_query={}
        )

        # Assert
        self.assertEqual(self.mock_repo_source.query_database.await_count, 2)
        self.assertEqual(result, [mock_page1, mock_page2])
        # Check that the cursor was passed correctly in the second call
        self.mock_repo_source.query_database.assert_has_awaits(
            [
                call(
                    data_source_id=db_info.DatabaseId,
                    page_size=unittest.mock.ANY,
                    filter_query={},
                    cursor=None,
                ),
                call(
                    data_source_id=db_info.DatabaseId,
                    page_size=unittest.mock.ANY,
                    filter_query={},
                    cursor="cursor1",
                ),
            ]
        )

    async def test_build_page_hierarchy_structure(self):
        """Test the structure of calls in build_page_hierarchy."""
        root_page = create_mock_page("root", "Root Page")
        sub_page = create_mock_page("sub1", "Sub Page 1")
        journal_page = create_mock_page("j1", "Journal Page 1", model=JournalPage)

        source_db = DatabaseInfo(DatabaseId="source-db")
        journal_db = DatabaseInfo(DatabaseId="journal-db")

        # Mock query_database to control the hierarchy
        async def mock_query_db(database_info, database_type, filter_query):
            page_id = filter_query["relation"]["contains"]
            if database_type == Page:
                if page_id == "root":
                    return [sub_page]  # root has one sub-page
                return []  # sub-page has no children
            if database_type == JournalPage:
                if page_id == "root":
                    return [journal_page]  # root has one journal page
                return []  # no other journals
            return []

        # Let the real process_source_recursive run, but mock its dependency (query_database)
        # and the methods it calls recursively to stop the recursion.
        with (
            patch.object(
                self.service, "query_database", side_effect=mock_query_db
            ) as mock_query,
            patch.object(
                self.service, "process_journal_recursive", new_callable=AsyncMock
            ) as mock_process_journal,
        ):
            # We need to patch process_source_recursive to stop it from
            # recursing infinitely in the test.
            # The side_effect will call the real method once, then do nothing.
            original_process_source = self.service.process_source_recursive

            async def side_effect_to_stop_recursion(*args, **kwargs):
                # The first call is for the root page. Let it run.
                if mock_process_source.call_count == 1:
                    return await original_process_source(*args, **kwargs)
                # Subsequent calls (for sub_page) will do nothing, stopping recursion.
                return

            with patch.object(
                self.service,
                "process_source_recursive",
                side_effect=side_effect_to_stop_recursion,
            ) as mock_process_source:
                await self.service.build_page_hierarchy(
                    root_page, source_db, journal_db, JournalRelations.BACKTRACK
                )

                # Assertions
                self.assertIsNotNone(root_page.Relations)
                self.assertEqual(root_page.Relations.Descendants, [sub_page])
                self.assertEqual(root_page.Relations.Journals, [journal_page])

                # Check that query_database was called for sub-pages and journal pages of root
                mock_query.assert_has_calls(
                    [
                        call(
                            database_info=source_db,
                            database_type=Page,
                            filter_query={
                                "property": "Ancestors",
                                "relation": {"contains": "root"},
                            },
                        ),
                        call(
                            database_info=journal_db,
                            database_type=JournalPage,
                            filter_query={
                                "property": "Backtrack",
                                "relation": {"contains": "root"},
                            },
                        ),
                    ],
                    any_order=True,
                )

                # Check recursive calls were initiated
                self.assertEqual(mock_process_source.call_count, 2)  # root + sub_page
                mock_process_journal.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
