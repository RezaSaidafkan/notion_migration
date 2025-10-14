from typing import AsyncGenerator, List

import pprint

from src.service.service_page_interface import ServicePageInterface
from src.repo.repo_page_interface import RepoPageInterface
from src.models.client_models import ClientPage, ClientPageRelations
import asyncio
from time import perf_counter


class ServicePage(ServicePageInterface):
    """
    Service layer for page-related domain logic.

    Keep schema- and business-logic here. The repository should expose
    generic persistence queries (like `query_database`) without hardcoding
    domain property names.
    """

    def __init__(self, repo: RepoPageInterface) -> None:
        self._repo = repo
    
    async def get_page(self, page_id: str) -> ClientPage:
        return await self._repo.get_page(page_id)

    async def build_page_hierarchy(self, root_page: ClientPage, source_database_id: str, journal_database_id: str, journal_db_relation: str, level: int = 0) -> List[ClientPage]:
        """
        Return pages whose 'Ancestor' relation contains the given parent.

        This method contains the schema knowledge ('Ancestor' relation) and
        delegates to the repository's generic `query_database` method.
        """
        async def _timed(coro, page: ClientPage, label: str):
            t0 = perf_counter()
            res = await coro
            t1 = perf_counter()
            print(f"[TIMING] {label} page={page.id} took={t1-t0:.3f}s")
            return res
        
        collected: list[ClientPage] = []

        async def process(page: ClientPage, level: int, tg: asyncio.TaskGroup):
            # create the coroutines and run them concurrently with timing
            sub_coro = self._repo.query_database(
                database_id=source_database_id,
                filter={
                    "property": "Ancestors",
                    "relation": {"contains": page.id},
                },
            )
            journ_coro = self._repo.query_database(
                database_id=journal_database_id,
                filter={
                    "property": journal_db_relation,
                    "relation": {"contains": page.id},
                },
            )

            sub_pages_tasks, journal_pages_tasks = await asyncio.gather(
                _timed(sub_coro, page, "query_database:sub_pages"),
                _timed(journ_coro, page, "query_database:journal_pages")
            )

            page.relations = ClientPageRelations(Descendants=None, Ancestors=None, Journals=None)
            if journal_pages_tasks:
                page.relations.Journals = journal_pages_tasks

            if sub_pages_tasks:
                page.relations.Descendants = sub_pages_tasks
                for sub_page in page.relations.Descendants:
                    tg.create_task(process(sub_page, level + 1, tg))

            if level == 1:
                pprint.pprint(page)
                collected.append(page)
                
                
        async with asyncio.TaskGroup() as tg:
            tg.create_task(process(root_page, level, tg))
            
        return collected
  
    async def create_or_update_page(self, page: ClientPage) -> ClientPage:
        raise NotImplementedError("This method should be implemented in the service layer.")

    async def add_relations_to_page(self, page: ClientPage, relations: List[str]) -> None:
        raise NotImplementedError("This method should be implemented in the service layer.")

    async def remove_relations_from_page(self, page: ClientPage, relations: List[str]) -> None:
        raise NotImplementedError("This method should be implemented in the service layer.")

    async def migrate_page(self, page: ClientPage, sourceDatabaseId: str, destinationDatabaseId: str) -> None:
        raise NotImplementedError("This method should be implemented in the service layer.")

    async def migrate_pages(self, pages: List[ClientPage], sourceDatabaseId: str, destinationDatabaseId: str) -> None:
        raise NotImplementedError("This method should be implemented in the service layer.")

    async def verify_page_migration(self, page: ClientPage) -> ClientPage:
        raise NotImplementedError("This method should be implemented in the service layer.")

    async def migrate_all_pages(self) -> None:
        raise NotImplementedError("This method should be implemented in the service layer.")
