import enum
from typing import AsyncGenerator, List, Literal, Union
from src.domain_conversion.definitions import ClientJournalRelations, ClientSourceRelations
import pprint
from collections.abc import Coroutine
from src.service.service_page_interface import ServicePageInterface
from src.repo.repo_page_interface import RepoPageInterface, PaginationResult
from src.models.client_models import ClientJournalPage, ClientPage, ClientRelation, JournalRelation
from src.constants.literal_definitions import DatabaseName, JournalName
import asyncio
from asyncio import Task
from time import perf_counter
from src.config.load_config import GLOBAL_CONFIG

class ServicePage(ServicePageInterface):
    """
    Service layer for page-related domain logic.

    Keep schema- and business-logic here. The repository should expose
    generic persistence queries (like `query_database`) without hardcoding
    domain property names.
    """

    def __init__(self, repo: RepoPageInterface) -> None:
        self._repo = repo

    async def get_page(self, page_id: str, database: Union[DatabaseName, JournalName]) -> ClientPage:
        return await self._repo.get_page(page_id, database)

    async def query_database(self, database_id: str, database: Union[DatabaseName, JournalName], filter: dict, tg: asyncio.TaskGroup, cursor=None) -> List[ClientPage]:
        exhausted = False
        pages: List[ClientPage] = []
        pagination: PaginationResult
        while not exhausted:
            task = tg.create_task(
                self._repo.query_database(database_id, 
                                          database, 
                                          page_size=GLOBAL_CONFIG.PAGE_SIZE,
                                          filter=filter, 
                                          cursor=cursor)
            )
            pagination = await task
            pages.extend(pagination.results)
            cursor = pagination.next_cursor
            exhausted = not pagination.has_more
        return pages

    async def build_page_hierarchy(self, root_page: ClientPage, source_database_id: str, source_db_name: DatabaseName, journal_database_id: str, journal_db_name: JournalName, level: int = 0) -> List[ClientPage]:
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

        async def process_journal_recursive(
            page: ClientJournalPage,
            journal_database_id: str, 
            journal_db_name: JournalName,
            journal_relation: ClientJournalRelations,
            tg: asyncio.TaskGroup,
            semaphore: asyncio.Semaphore
            ):
            async with semaphore:
                sub_journal_pages = await self.query_database(
                    database_id=journal_database_id,
                    database=journal_db_name,
                    filter={
                        "property": journal_relation.ANCESTORS.value,
                        "relation": {"contains": page.id},
                    },
                    tg=tg,
                )

                if sub_journal_pages:
                    page.relations = JournalRelation(Descendants=sub_journal_pages, Ancestors=page)
                    for journ_page in sub_journal_pages:
                        tg.create_task(
                            _timed(
                                process_journal_recursive(
                                    journ_page,
                                    journal_database_id,
                                    journal_db_name, 
                                    journal_relation, 
                                    tg,
                                    semaphore),
                                journ_page,
                                "process_journal_recursive"
                            )
                        )

        async def process_source_recursive(
            page: ClientPage, 
            source_database_id: str, 
            source_db_name: DatabaseName, 
            journal_database_id: str,
            journal_db_name: JournalName, 
            level: int,
            tg: asyncio.TaskGroup,
            semaphore: asyncio.Semaphore
            ):
            # create the coroutines and run them concurrently with timing
            
            async with semaphore:
                sub_pages_tasks = tg.create_task(
                    _timed(
                        self.query_database(
                            database_id=source_database_id,
                            database=source_db_name,
                            filter={
                                "property": ClientSourceRelations.ANCESTORS.value,
                                "relation": {"contains": page.id},
                                },
                            tg=tg,
                        ),
                            page,
                            "query_database:sub_pages"
                        )
                )

                journal_roots_tasks = tg.create_task(
                    _timed(
                        self.query_database(
                            database_id=journal_database_id,
                            database=journal_db_name,
                            filter={
                                "property": source_db_name.value,
                                "relation": {"contains": page.id},
                            },
                            tg=tg,
                        ),
                        page,
                        "query_database:journal_roots"
                    )
                )

                sub_pages, journal_pages = await asyncio.gather(sub_pages_tasks, journal_roots_tasks)

                page.relations = ClientRelation(Descendants=None, Ancestors=None, Journals=None)
                if journal_pages:
                    page.relations.Journals = journal_pages
                    for journ_page in journal_pages:
                        tg.create_task(
                            _timed(
                                process_journal_recursive(
                                    journ_page, 
                                    journal_database_id,
                                    journal_db_name,
                                    ClientJournalRelations,
                                    tg,
                                    semaphore
                                ),
                                journ_page,
                                "process_journal_recursive"
                            )
                    )

                sub_pages, journal_pages = await asyncio.gather(sub_pages_tasks, journal_roots_tasks)

                page.relations = ClientRelation(Descendants=None, Ancestors=None, Journals=None)
                if journal_pages:
                    page.relations.Journals = journal_pages
                    for journ_page in journal_pages:
                        tg.create_task(
                            _timed(
                                process_journal_recursive(
                                    journ_page,
                                    journal_database_id,
                                    journal_db_name,
                                    ClientJournalRelations,
                                    tg,
                                    semaphore
                                ),
                                journ_page,
                                "process_journal_recursive"
                            )
                        )

                if sub_pages:
                    page.relations.Descendants = sub_pages
                    for sub_page in page.relations.Descendants:
                        tg.create_task(
                            _timed(
                                process_source_recursive(
                                    sub_page,
                                    source_database_id,
                                    source_db_name,
                                    journal_database_id,
                                    journal_db_name,
                                    level + 1,
                                    tg, 
                                    semaphore
                                ),
                                sub_page,
                                "process_source_recursive"
                            )
                        )

            if level == 1:
                pprint.pprint(page)
                collected.append(page)


        sem = asyncio.Semaphore(10)
        async with asyncio.TaskGroup() as tg:
            tg.create_task(
                process_source_recursive(
                    root_page, 
                    source_database_id, 
                    source_db_name, 
                    journal_database_id,
                    journal_db_name, 
                    level, 
                    tg,
                    semaphore=sem
                    )
                )
            
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
