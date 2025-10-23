import enum
from typing import AsyncGenerator, List, Literal, Union
import pprint
from collections.abc import Coroutine
from src.service.service_page_interface import ServicePageInterface
from src.repo.repo_page_interface import RepoPageInterface, PaginationResult
from src.models.client_models import Page, JournalPage, CommonPage, PageRelation, JournalRelation
from src.constants.literal_definitions import JournalRelations, DatabaseName, SourceRelations
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

    async def get_page(self, page_id: str, database: DatabaseName) -> CommonPage:
        return await self._repo.get_page(page_id, database)

    async def get_source_page(self, page_id: str) -> Page:
        return await self.get_page(page_id, DatabaseName.SOURCE)
    
    async def query_database(self, database_id: str, database_name: DatabaseName, filter: dict) -> List[CommonPage]:
        exhausted = False
        cursor = None
        pages: List[CommonPage] = []
        pagination: PaginationResult
        while not exhausted:
            pagination = await self._repo.query_database(
                database_id, 
                database_name, 
                page_size=GLOBAL_CONFIG.PAGE_SIZE,
                filter=filter, 
                cursor=cursor
                )
            pages.extend(pagination.results)
            cursor = pagination.next_cursor
            exhausted = not pagination.has_more
        return pages

    async def build_page_hierarchy(self,
                                   root_page: Page, 
                                   source_database_id: str, 
                                   journal_database_id: str, 
                                   journal_relation: JournalRelations,
                                   level: int = 0) -> List[CommonPage]:
        """
        Return pages whose 'Ancestor' relation contains the given parent.

        This method contains the schema knowledge ('Ancestor' relation) and
        delegates to the repository's generic `query_database` method.
        """
        collected: list[CommonPage] = []
        async def process_source_recursive(
            page: Page, 
            source_database_id: str, 
            journal_database_id: str,
            journal_relation: JournalRelation,
            level: int,
            tg: asyncio.TaskGroup,
            semaphore: asyncio.Semaphore
            ):
            # create the coroutines and run them concurrently with timing
            
            sub_pages_tasks = self.get_sub_pages(
                parent_page=page,
                source_database_id=source_database_id,
                tg=tg
                )
            
            journal_database_tasks = self.get_journal_root_pages(
                source_page=page,
                journal_database_id=journal_database_id,
                journal_relation=journal_relation,
                tg=tg
                )

            sub_pages, journal_database_pages = await asyncio.gather(sub_pages_tasks, journal_database_tasks)

            page.Relations = PageRelation(Descendants=None, Ancestors=None, Journals=None)
            
            if journal_database_pages:
                page.Relations.Journals = journal_database_pages
                # for journ_page in journal_database_pages:
                #     tg.create_task(
                #         _timed(
                #             _limited(
                #                 semaphore,
                #                 self.process_journal_recursive(
                #                     journ_page,
                #                     journal_database_id,
                #                     journal_db_name,
                #                     ClientJournalRelations,
                #                     tg,
                #                     semaphore
                #                 ),
                #             ),
                #             journ_page,
                #             "process_journal_recursive"
                #         )
                #     )

            if sub_pages:
                page.Relations.Descendants = sub_pages
                for sub_page in page.Relations.Descendants:
                    tg.create_task(
                        _timed(
                            _limited(
                                semaphore,
                                process_source_recursive(
                                    sub_page,
                                    source_database_id,
                                    journal_database_id,
                                    journal_relation,
                                    level + 1,
                                    tg, 
                                    semaphore
                                ),
                            ),
                            sub_page,
                            "process_source_recursive"
                        )
                    )

            if level == 1:
                pprint.pprint(page)
                collected.append(page)


        semaphore = asyncio.Semaphore(GLOBAL_CONFIG.SEMAPHORE_LIMIT)
        async with asyncio.TaskGroup() as tg:
            tg.create_task(
                process_source_recursive(
                    root_page, 
                    source_database_id, 
                    journal_database_id,
                    journal_relation,
                    level, 
                    tg,
                    semaphore,
                    )
                )
            
        return collected
    
    def get_sub_pages(self, 
                      parent_page: Page, 
                      source_database_id: str, 
                      tg: asyncio.TaskGroup
                      ) -> Task[List[Page]]:
        return tg.create_task(
                _timed(
                    self.query_database(
                        database_id=source_database_id,
                        database_name=DatabaseName.SOURCE,
                        filter={
                            "property": SourceRelations.JOURNALS.value,
                            "relation": {"contains": parent_page.Id},
                            },
                    ),
                    parent_page,
                    "query_database:sub_pages"
                    ),
                )

    def get_journal_root_pages(self,
                               source_page: Page,
                               journal_database_id: str, 
                               journal_relation: JournalRelations,
                               tg: asyncio.TaskGroup
                               ) -> Task[List[JournalPage]]:
        return tg.create_task(
                _timed(
                    self.query_database(
                        database_id=journal_database_id,
                        database_name=DatabaseName.JOURNAL.value,
                        filter={
                            "property": journal_relation.value,
                            "relation": {"contains": source_page.Id},
                        },
                    ),
                    source_page,
                    "query_database:journal_roots"
                    ),
                )
        

    async def process_journal_recursive(
                                        self,
                                        page: JournalPage,
                                        journal_database_id: str, 
                                        journal_db: JournalRelation,
                                        tg: asyncio.TaskGroup,
                                        semaphore: asyncio.Semaphore
                                        ):
        '''
        This function processes a journal page recursively, fetching its sub-journal pages.
        Assigns the found sub-journal pages to the Relations.Descendants / Relations.Ancestors attributes of the page.
        '''
        sub_journal_pages = await self.query_database(
            database_id=journal_database_id,
            database_name=journal_db,
            filter={
                "property": journal_db.RELATION.value,
                "relation": {"contains": page.Id},
            },
        )

        if sub_journal_pages:
            page.Relations = JournalRelation(Descendants=sub_journal_pages, Ancestors=page)
            for journ_page in sub_journal_pages:
                tg.create_task(
                    _timed(
                        _limited(
                            semaphore,
                            self.process_journal_recursive(
                                journ_page,
                                journal_database_id,
                                journal_db,
                                tg,
                                semaphore),
                        ),
                        journ_page,
                        "process_journal_recursive"
                    )
                )


    
    async def create_or_update_page(self, page: CommonPage) -> CommonPage:
        raise NotImplementedError("This method should be implemented in the service layer.")

    async def add_relations_to_page(self, page: CommonPage, relations: List[str]) -> None:
        raise NotImplementedError("This method should be implemented in the service layer.")

    async def remove_relations_from_page(self, page: CommonPage, relations: List[str]) -> None:
        raise NotImplementedError("This method should be implemented in the service layer.")

    async def migrate_page(self, page: CommonPage, sourceDatabaseId: str, destinationDatabaseId: str) -> None:
        raise NotImplementedError("This method should be implemented in the service layer.")

    async def migrate_pages(self, pages: List[CommonPage], sourceDatabaseId: str, destinationDatabaseId: str) -> None:
        raise NotImplementedError("This method should be implemented in the service layer.")

    async def verify_page_migration(self, page: CommonPage) -> CommonPage:
        raise NotImplementedError("This method should be implemented in the service layer.")

    async def migrate_all_pages(self) -> None:
        raise NotImplementedError("This method should be implemented in the service layer.")


async def _limited(semaphore: asyncio.Semaphore, coro):
    async with semaphore:
        return await coro


async def _timed(coro, page: CommonPage, label: str, debug: bool = GLOBAL_CONFIG.DEBUG) -> any:
    if debug:
        t0 = perf_counter()
        res = await coro
        t1 = perf_counter()
        print(f"[TIMING] {label} page={page.Id.replace('-', ''), page.Properties.Title.title} took={t1-t0:.3f}s")
    else:
        res = await coro
    return res
