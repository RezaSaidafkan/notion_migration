from typing import AsyncGenerator, List

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

    async def build_page_hierarchy(self, page: ClientPage, source_database_id: str, journal_database_id: str, journal_db_relation: str, level: int = 0) -> AsyncGenerator[ClientPage, None]:
        """Return pages whose 'Ancestor' relation contains the given parent.

        This method contains the schema knowledge ('Ancestor' relation) and
        delegates to the repository's generic `query_database` method.
        """
        sub_pages_task = asyncio.create_task(
            self._repo.query_database(
            database_id=source_database_id,
            filter={
                "property": "Ancestors",
                "relation": {"contains": page.id},
            },
            ),
        )
        journal_pages_task = asyncio.create_task(
            self._repo.query_database(
            database_id=journal_database_id,
            filter={
                "property": journal_db_relation,
                "relation": {"contains": page.id},
            },
            ),
        )
        
        # run both DB queries concurrently and report individual timings from _timed
        sub_pages, journal_pages = await asyncio.gather(sub_pages_task, journal_pages_task)

        page.relations = ClientPageRelations(Descendants=None, Ancestors=None, Journals=None)
        
        if journal_pages:
            page.relations.Journals = journal_pages

        if sub_pages:
            print(f"[TRACE] page={page.id} level={level} sub_pages={len(sub_pages)}")
            # refresh the relations on the parent page to include the fetched children
            page.relations.Descendants=sub_pages
            
            for sub_page in sub_pages:
                async for item in self.build_page_hierarchy(sub_page, source_database_id, journal_database_id, journal_db_relation, level + 1):
                    yield item
            
            # sub_pages_tasks = []
            # for sub_page in sub_pages:
            #     sub_pages_tasks.append(asyncio.create_task(self.build_page_hierarchy(sub_page, source_database_id, journal_database_id, level + 1)))
            
            #     for sub_page_task in asyncio.as_completed(sub_pages_tasks):
            #         async for item in await sub_page_task:
            #             yield item
            
            # sub_pages_tasks = []
            # for sub_page in sub_pages:
            #     sub_pages_tasks.append([asyncio.create_task(p) async for p in self.build_page_hierarchy(sub_page, source_database_id, journal_db_id, level + 1)])
            #     # asyncio.gather(*[item for sublist in sub_pages_tasks for item in sublist])
            #     asyncio.gather(*sub_pages_tasks)

            # sub_pages_tasks = []
            # for sub_page in sub_pages:
            #     async for item in self.build_page_hierarchy(sub_page, source_database_id, journal_db_id, level + 1):
            #         asyncio.create_task(item)
            #         sub_pages_tasks.append(item)
                    
            #     # asyncio.gather(*[item for sublist in sub_pages_tasks for item in sublist])
            #     asyncio.gather(*sub_pages_tasks)

        if level == 1:
            yield page

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
    