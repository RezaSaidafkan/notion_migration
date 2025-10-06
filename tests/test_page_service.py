from typing import List, Dict, Any

from src.notion_migration.service.page_service import PageService
from src.notion_migration.models.client_models import ClientPage


class FakeRepo:
    def __init__(self):
        self.called_with = None

    def query_database(self, database_id: str, filter: Dict[str, Any] = None) -> List[ClientPage]:
        self.called_with = {"database_id": database_id, "filter": filter}
        return []


def test_query_descendants_of_parent_delegates_to_repo():
    fake = FakeRepo()
    svc = PageService(repo=fake)

    svc.query_descendants_of_parent(parent_page_id="parent-123", database_id="db-abc")

    assert fake.called_with is not None
    assert fake.called_with["database_id"] == "db-abc"
    assert fake.called_with["filter"]["property"] == "Ancestor"
    assert fake.called_with["filter"]["relation"]["contains"] == "parent-123"
