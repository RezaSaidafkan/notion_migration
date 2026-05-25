from common_libs.models.api_models import ApiTaskPage, ApiJournalPage
from common_libs.models.client_models import BasePage
from uuid import UUID


def create_mock_api_task_page(page: BasePage, title: str) -> ApiTaskPage:
    """Helper function to create a mock raw API page dictionary."""
    return ApiTaskPage.model_validate(
        {
            "id": str(page.Id.Id),
            "created_time": "2022-01-01T00:00:00.000Z",
            "last_edited_time": "2022-01-01T00:00:00.000Z",
            "parent": {
                "type": "data_source_id",
                "data_source_id": UUID('{12345678-1234-5678-1234-567812345678}')},
            "archived": False,
            "icon": None,
            "properties": {
                "Title": {
                    "id": "title_id",
                    "type": "title",
                    "title": [
                        {
                            "type": "text",
                            "text": {
                                "content": title,
                                "link": None},
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
            },
        })

def create_mock_api_journal_page(page: BasePage, title: str) -> ApiJournalPage:
    """Helper function to create a mock raw API page dictionary."""
    return ApiJournalPage.model_validate(
        {
            "id": str(page.Id.Id),
            "created_time": "2022-01-01T00:00:00.000Z",
            "last_edited_time": "2022-01-01T00:00:00.000Z",
            "parent": {
                "type": "data_source_id",
                "data_source_id": UUID('{12345678-1234-5678-1234-567812345678}')},
            "archived": False,
            "icon": None,
            "properties": {
                "Title": {
                    "id": "title_id",
                    "type": "title",
                    "title": [
                        {
                            "type": "text",
                            "text": {
                                "content": title,
                                "link": None},
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
                "Priority": None,
                "Urgency": None,
                "Description": None,
            }
        })

def create_mock_api_journal_update(page: BasePage, title: str) -> ApiJournalPage:
    return ApiJournalPage.model_validate(
        {
            "id": str(page.Id.Id),
            "properties": {
                "Title": {
                        "id": "title_id",
                        "type": "title",
                        "title": [
                            {
                                "type": "text",
                                "text": {
                                    "content": title,
                                    "link": None
                                },
                                "plain_text": title,
                                }
                        ],
                },
                "Status": {
                    "id": "status_id",
                    "type": "status",
                    "status": {
                        "name": "Completed"
                    },
                    'select': None
                },
                "Timeline": {
                    "id": "date_id",
                    "type": "date",
                    "date": {"start": "2023-01-01", "end": None, "time_zone": None},
                },
                "Type": {
                    "id": "type_id",
                    "type": "select",
                    "select": {"id": "select_id", "name": "Task", "color": "blue"},
                },
            },
            "icon": {
                "type": "emoji",
                "emoji": "🎉",
            },
            "cover": {
                "type": "external",
                "external": {
                    "url": "https://example.com/cover.png"
                }
            },
            "archived": False,
            "is_locked": False,
            "in_trash": False,
            "created_time": "2022-01-01T00:00:00.000Z",
            "last_edited_time": "2022-01-01T00:00:00.000Z",
            "parent": {
                "type": "data_source_id",
                "data_source_id": UUID('{12345678-1234-5678-1234-567812345678}')
                },
        })
