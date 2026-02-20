# pylint: disable=all
import unittest
from unittest.mock import AsyncMock, call, patch
from uuid import UUID

from common_libs.constants.literal_definitions import (
                                                       RelationDefinitions, TaskRelationsDefinition, JournalRelationsDefinition, JunctionRelationDefinition)
from common_libs.models.api_models import TitleItem, TitleProperty, TitleText
from common_libs.models.client_models import (JournalPage,
                                              JournalProperties, TaskPage,
                                              PageId, TaskProperties, 
                                              PaginationResult,
                                              B)
from common_libs.models.context import DatasourceInfo, MigrationContext, ExecutionContext
from migration_engine.service.service_page_notion import ServicePage
from migration_engine.repo.repo_page_notion import NotionRepoJournal, NotionRepoSource


def create_mock_page(
    page_id: UUID, title: str, model: type[TaskPage] | type[JournalPage] = TaskPage
) -> TaskPage | JournalPage:
    """Helper to create a mock Page or JournalPage."""
    mock_title = TitleProperty(
        id="title_id",
        type="title",
        title=[TitleItem(type="text", text=TitleText(content=title, link=None))],
    )
    properties: TaskProperties | JournalProperties
    if model == TaskPage:
        properties = TaskProperties(
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
        properties = JournalProperties(
            Title=mock_title,
            Type=None,
            Status=None,
            Timeline=None,
            Description=None,
        )
    return model(Id=PageId(Id=page_id), Icon=None, Properties=properties)


class TestServicePage(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Arrange: Global
        mock_repo_source = AsyncMock(spec=NotionRepoSource)
        mock_repo_source.query_database = AsyncMock()
        mock_repo_journal = AsyncMock(spec=NotionRepoJournal)
        mock_repo_journal.query_database = AsyncMock()
        mock_repo_target = AsyncMock(spec=NotionRepoSource)
        mock_repo_target.query_database = AsyncMock()
        
        source_datasource_id = UUID('{12345678-1234-5678-1234-567812345678}')
        journal_datasource_id = UUID('{22345678-1234-5678-1234-567812345678}')
        target_datasource_id = UUID('{32345678-1234-5678-1234-567812345678}')
        
        self.migration_context = MigrationContext[PageId, TaskPage, JournalPage, RelationDefinitions](
            source_datasource_info=DatasourceInfo(
                datasource_id=source_datasource_id,
                repo=mock_repo_source),
            journal_datasource_info=DatasourceInfo(
                datasource_id=journal_datasource_id,
                repo=mock_repo_journal),
            target_datasource_info=DatasourceInfo(
                datasource_id=target_datasource_id,
                repo=mock_repo_target),
            task_relation_definition=TaskRelationsDefinition.ANCESTORS,
            journal_relation_definition=JournalRelationsDefinition.ANCESTOR,
            junction_relation_definition=JunctionRelationDefinition.LIFE_STYLE,
        )
        
        self.execution_context = ExecutionContext(page_size=10, debug=True)
        
        self.service = ServicePage()

    async def test_refresh_from_backend(self):
        """Test that refresh_from_backend calls the source repo and returns a Page."""
        # Arrange
        page_id = PageId(Id=UUID('{22345678-1234-5678-1234-567812345678}'))
        mock_page = create_mock_page(page_id.Id, "Test Page")
        self.migration_context.source_datasource_info.repo.read_page.return_value = mock_page

        # Act
        result = await self.service.read_page(page_id, self.execution_context, self.migration_context)

        # Assert
        self.migration_context.source_datasource_info.repo.read_page.assert_awaited_once_with(page_id)
        self.assertIsInstance(result, TaskPage)
        self.assertEqual(result.Id, page_id)
        self.assertEqual(result.Properties.Title, mock_page.Properties.Title)

    async def test_query_database_for_source_pages(self):
        """Test querying for Page types uses the source repo."""
        # Arrange
        page_id = UUID('{42345678-1234-5678-1234-567812345678}')
        mock_task_page = create_mock_page(page_id, "Page 1", model=TaskPage)
            
        self.migration_context.source_datasource_info.repo.query_database.return_value = PaginationResult[TaskPage](
            results=[mock_task_page], has_more=False, next_cursor=None
        )

        # Act
        result = await self.service.query_database(
            page_id=mock_task_page.Id,
            relation=TaskRelationsDefinition.ANCESTORS,
            datasource_info=self.migration_context.source_datasource_info,
            execution_context=self.execution_context)

        # Assert
        self.migration_context.source_datasource_info.repo.query_database.assert_awaited_once()
        self.migration_context.journal_datasource_info.repo.query_database.assert_not_awaited()
        self.assertEqual(result, [mock_task_page])

    async def test_query_database_for_journal_pages(self):
        """Test querying for JournalPage types uses the journal repo."""
        # Arrange
        # Arrange
        page_id = UUID('{52345678-1234-5678-1234-567812345678}')
        mock_journal_page = create_mock_page(page_id, "Page 1", model=JournalPage)
        
        self.migration_context.journal_datasource_info.repo.query_database.return_value = PaginationResult[JournalPage](
            results=[mock_journal_page], has_more=False, next_cursor=None
        )
        
        # Act
        result = await self.service.query_database(
            page_id=mock_journal_page.Id,
            relation=JournalRelationsDefinition.ANCESTOR,
            datasource_info=self.migration_context.journal_datasource_info,
            execution_context=self.execution_context)

        # Assert
        self.migration_context.journal_datasource_info.repo.query_database.assert_awaited_once()
        self.migration_context.source_datasource_info.repo.query_database.assert_not_awaited()
        self.assertEqual(result, [mock_journal_page])

    async def test_query_database_with_pagination(self):
        """Test that query_database handles pagination correctly."""
        # Arrange
        mock_parent_page = create_mock_page(
            UUID("62345678-1234-5678-1234-567812345678"),
            "MockParentPage",
            TaskPage)
        
        mock_page_1 = create_mock_page(
            UUID("72345678-1234-5678-1234-567812345678"),
            "MockPage 1",
            TaskPage)
        
        mock_page_2 = create_mock_page(
            UUID("82345678-1234-5678-1234-567812345678"),
            "MockPage 2",
            TaskPage)
        
        self.migration_context.source_datasource_info.repo.query_database.side_effect = [
            PaginationResult(
                results=[mock_page_1], has_more=True, next_cursor="cursor1"
            ),
            PaginationResult(
                results=[mock_page_2], has_more=False, next_cursor=None),
        ]

        # Act
        result = await self.service.query_database(
            mock_parent_page.Id,
            self.migration_context.task_relation_definition,
            self.migration_context.source_datasource_info,
            self.execution_context
        )

        # Assert
        self.assertEqual(self.migration_context.source_datasource_info.repo.query_database.await_count, 2)
        self.assertEqual(result, [mock_page_1, mock_page_2])
        # Check that the cursor was passed correctly in the second call
        self.migration_context.source_datasource_info.repo.query_database.assert_has_awaits(
            [
                call(
                    page_id=mock_parent_page.Id,
                    relation=TaskRelationsDefinition.ANCESTORS,
                    data_source_id=self.migration_context.source_datasource_info.datasource_id,
                    cursor=None,
                    execution_context=self.execution_context,
                ),
                call(
                    page_id=mock_parent_page.Id,
                    relation=TaskRelationsDefinition.ANCESTORS,
                    data_source_id=self.migration_context.source_datasource_info.datasource_id,
                    cursor="cursor1",
                    execution_context=self.execution_context,
                ),
            ]
        )

    async def test_build_page_hierarchy_structure(self):
        # Arrange
        """Test the structure of calls in build_page_hierarchy."""
        root_page_uuid = UUID('{12345678-1234-5678-1234-567812345678}')
        root_page = create_mock_page(
            root_page_uuid,
            "Root Page",
            model=TaskPage)
        sub_page = create_mock_page(
            UUID('{22345678-1234-5678-1234-567812345678}'),
            "Sub Task Page 1",
            model=TaskPage)
        journal_page = create_mock_page(
            UUID('{32345678-1234-5678-1234-567812345678}'),
            "Journal Page 1",
            model=JournalPage)

        # Mock query_database to control the hierarchy
        async def mock_query_db(page_id: PageId, relation: RelationDefinitions, datasource_info: DatasourceInfo[PageId, B, RelationDefinitions], execution_context: ExecutionContext):
            if isinstance(datasource_info.repo, NotionRepoSource):
                if page_id.Id == root_page_uuid:
                    return [sub_page]  # root has one sub-page
                return []  # sub-page has no children
            if isinstance(datasource_info.repo, NotionRepoJournal):
                if page_id.Id == root_page_uuid:
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
                # Act
                await self.service.build_page_hierarchy(root_page, self.migration_context, self.execution_context)

                # Assertions
                self.assertIsNotNone(root_page.Relations)
                self.assertEqual(root_page.Relations.Descendants, [sub_page])
                self.assertEqual(root_page.Relations.Journals, [journal_page])

                # Check that query_database was called for sub-pages and journal pages of root
                mock_query.assert_has_calls(
                    [
                        call(
                            page_id=root_page.Id,
                            relation=TaskRelationsDefinition.ANCESTORS,
                            datasource_info=self.migration_context.source_datasource_info,
                            execution_context=self.execution_context
                        ),
                        call(
                            page_id=root_page.Id,
                            relation=JunctionRelationDefinition.LIFE_STYLE,
                            datasource_info=self.migration_context.journal_datasource_info,
                            execution_context=self.execution_context
                        ),
                    ],
                    any_order=True,
                )

                # Check recursive calls were initiated
                self.assertEqual(mock_process_source.call_count, 2)  # root + sub_page
                mock_process_journal.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
