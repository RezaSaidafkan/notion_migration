import unittest
from unittest.mock import AsyncMock, patch
from uuid import UUID

from common_libs.models.api_models import TitleItem, TitleProperty, TitleText
from common_libs.models.client_models import Page, PageId, PageProperties
from migration_engine.utils.timer import _timed

def create_mock_page(page_id: UUID, title: str) -> Page:
    """Helper to create a mock Page."""
    mock_title = TitleProperty(
        id="title_id",
        type="title",
        title=[TitleItem(type="text", text=TitleText(content=title, link=None))],
    )
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
    return Page(Id=PageId(Id=page_id), Icon=None, Properties=properties)


class TestTimer(unittest.IsolatedAsyncioTestCase):
    async def test_timed_debug_on(self):
        mock_coro = AsyncMock(return_value="coro_result")
        label = "test_label"

        with patch("builtins.print") as mock_print:
            with patch("migration_engine.utils.timer.GLOBAL_CONFIG") as mock_config:
                mock_config.debug = True

                # Create a mock page inside the test to avoid issues with global scope
                mock_page = create_mock_page(
                    UUID('{12345678-1234-5678-1234-567812345678}'),
                    "Test Page")
                result = await _timed(mock_coro(), mock_page, label)
                mock_coro.assert_awaited_once()
                self.assertEqual(result, "coro_result")
                mock_print.assert_called_once()
                self.assertIn("[TIMING]", mock_print.call_args[0][0])
                self.assertIn(label, mock_print.call_args[0][0])
                self.assertIn(
                    str(mock_page.Id.Id), mock_print.call_args[0][0]
                )

    async def test_timed_debug_off(self):
        mock_coro = AsyncMock(return_value="coro_result")
        label = "test_label"

        with patch("builtins.print") as mock_print:
            with patch("migration_engine.utils.timer.GLOBAL_CONFIG") as mock_config:
                mock_config.debug = False

                # Create a mock page inside the test to avoid issues with global scope
                mock_page = create_mock_page(
                    UUID('{12345678-1234-5678-1234-567812345678}'),
                    "Test Page")
                result = await _timed(mock_coro(), mock_page, label)

                mock_coro.assert_awaited_once()
                self.assertEqual(result, "coro_result")
                mock_print.assert_not_called()
