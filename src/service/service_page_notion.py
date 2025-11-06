from typing import List, Union, Any, cast
import pprint
from src.service.service_page_interface import ServicePageInterface
from src.repo.repo_page_notion import (
    NotionRepoJournalPage,
    NotionRepoPage,
    NotionRepository,
)
from src.models.client_models import (
    Page,
    JournalPage,
    PageRelation,
    JournalRelation,
    K, P, DB, R
)
from src.constants.literal_definitions import (
    JournalRelations,
    SourceRelations,
    DatabaseInfo,
)
import asyncio
from asyncio import Task
from time import perf_counter
from src.config.load_config import GLOBAL_CONFIG


class ServicePage(ServicePageInterface[K, P, DB, R]):
    """
    Service layer for page-related domain logic.

    Keep schema- and business-logic here. The repository should expose
    generic persistence queries (like `query_database`) without hardcoding
    domain property names.
    """

    def __init__(
        self, repo_source: NotionRepoPage, repo_journal: NotionRepoJournalPage
    ) -> None:
        self._repo_source = repo_source
        self._repo_journal = repo_journal

    async def refresh_from_backend(self, page_id: K) -> P:
        retrieved_page = await self._repo_source.read_page(page_id)
        return cast(P, Page(
            Id=page_id, Icon=retrieved_page.Icon, Properties=retrieved_page.Properties
        ))

    def get_pages(
        self,
        page: P,
        database_info: DatabaseInfo,
        database_type: DB,
        relation: Union[SourceRelations, JournalRelations],
        tg: asyncio.TaskGroup,
    ) -> Task[List[P]]:
        
        return tg.create_task(
            _timed(
                self.query_database(
                    database_info=database_info,
                    database_type=database_type,
                    filter={
                        "property": relation.value,
                        "relation": {"contains": page.Id.Id},
                    },
                ),
                page,
                "query_database:sub_pages",
            ),
        )
    
    def get_source_pages(
        self,
        page: P,
        database_info: DatabaseInfo,
        relation: SourceRelations,
        tg: asyncio.TaskGroup) -> Task[List[P]]:
        return cast(
                Task[List[P]], 
                self.get_pages(
                    page=cast(P, page),
                    database_info=database_info,
                    database_type=cast(DB, Page),
                    relation=relation,
                    tg=tg
                    )
                )
    
    def get_journal_pages(self,
        page: P,
        database_info: DatabaseInfo,
        relation: JournalRelations,
        tg: asyncio.TaskGroup) -> Task[List[P]]:
        return cast(
                Task[List[P]],
                self.get_pages(
                    page=cast(P, page),
                    database_info=database_info,
                    database_type=cast(DB, JournalPage),
                    relation=relation,
                    tg=tg
                    )
                )
        

    async def query_database(
        self, database_info: DatabaseInfo, database_type: DB, filter: dict
    ) -> List[P]:
        repo: NotionRepository
        if database_type is Page:
            repo = self._repo_source
        elif database_type is JournalPage:
            repo = self._repo_journal
        else:
            # This branch is unreachable due to the overloads, but good for runtime safety
            raise TypeError(f"Unsupported database_type: {database_type}")

        exhausted = False
        cursor = None
        pages: List[P] = []

        while not exhausted:
            # The cast is safe because of the if/elif block above.
            pagination = await repo.query_database(
                database_id=database_info.DatabaseId,
                page_size=GLOBAL_CONFIG.PAGE_SIZE,
                filter=filter,
                cursor=cursor,
            )

            pages.extend(cast(List[P], pagination.results))
            cursor = pagination.next_cursor
            exhausted = not pagination.has_more
        return pages

    async def query_database2(
        self, database_info: DatabaseInfo, database_type: DB, filter: dict
    ) -> List[P]:
        raise RuntimeError
        
    async def build_page_hierarchy(
        self,
        root_page: P,
        source_database: DatabaseInfo,
        journal_database: DatabaseInfo,
        journal_relation: JournalRelations,
        level: int = 0,
    ) -> List[P]:
        """
        Return pages whose 'Ancestor' relation contains the given parent.

        This method contains the schema knowledge ('Ancestor' relation) and
        delegates to the repository's generic `query_database` method.
        """
        collected: list[P] = []

        semaphore = asyncio.Semaphore(GLOBAL_CONFIG.SEMAPHORE_LIMIT)
        async with asyncio.TaskGroup() as tg:
            tg.create_task(
                self.process_source_recursive(
                    root_page,
                    source_database,
                    journal_database,
                    journal_relation,
                    level,
                    collected,
                    tg,
                    semaphore,
                )
            )

        return collected

    async def process_source_recursive(
        self,
        page: P,
        source_database_info: DatabaseInfo,
        journal_database_info: DatabaseInfo,
        journal_relation: JournalRelations,
        level: int,
        collected: list[P],
        tg: asyncio.TaskGroup,
        semaphore: asyncio.Semaphore,
    ):
        # create the coroutines and run them concurrently with timing

        sub_pages_tasks: Task[List[P]] = self.get_source_pages(
        page=page,
        database_info=source_database_info,
        relation=SourceRelations.ANCESTORS,
        tg=tg,
        ) # type: ignore
        
        journal_database_tasks: Task[List[P]] = self.get_journal_pages(
            page=page,
            database_info=journal_database_info, 
            relation=journal_relation, 
            tg=tg
        ) # type: ignore

            
        sub_pages, journal_database_pages = await asyncio.gather(
            sub_pages_tasks, journal_database_tasks
        )
        page.Relations = PageRelation(Descendants=None, Ancestors=None, Journals=None)
        

        if journal_database_pages is not None:
            page.Relations.Journals = journal_database_pages
            for journ_page in journal_database_pages:
                tg.create_task(
                    _timed(
                        _limited(
                            semaphore,
                            self.process_journal_recursive(
                                journ_page,
                                journal_database_info,
                                journal_relation,
                                tg,
                                semaphore
                            ),
                        ),
                        journ_page,
                        "process_journal_recursive"
                    )
                )

        if sub_pages is not None:
            page.Relations.Descendants = sub_pages
            for sub_page in sub_pages:
                tg.create_task(
                    _timed(
                        _limited(
                            semaphore,
                            self.process_source_recursive(
                                sub_page,
                                source_database_info,
                                journal_database_info,
                                journal_relation,
                                level + 1,
                                collected,
                                tg,
                                semaphore,
                            ),
                        ),
                        sub_page,
                        "process_source_recursive",
                    )
                )

        if level == 1:
            pprint.pprint(page)
            collected.append(page)

    async def process_journal_recursive(
        self,
        page: P,
        journal_database_info: DatabaseInfo,
        journal_relation: JournalRelations,
        tg: asyncio.TaskGroup,
        semaphore: asyncio.Semaphore,
    ):
        """
        This function processes a journal page recursively, fetching its sub-journal pages.
        Assigns the found sub-journal pages to the Relations.Descendants / Relations.Ancestors attributes of the page.
        """
        sub_journal_pages: List[P] = await self.get_journal_pages(
            page=page,
            database_info=journal_database_info,
            relation=JournalRelations.ANCESTORS,
            tg=tg
        )

        if sub_journal_pages:
            page.Relations = JournalRelation(
                Descendants=cast(List[P], sub_journal_pages),
                Ancestors=cast(List[P], [page]),
            )
            for journ_page in sub_journal_pages:
                tg.create_task(
                    _timed(
                        _limited(
                            semaphore,
                            self.process_journal_recursive(
                                journ_page,
                                journal_database_info,
                                journal_relation,
                                tg,
                                semaphore,
                            ),
                        ),
                        journ_page,
                        "process_journal_recursive",
                    )
                )

    async def create_or_update_page(self, page: P) -> bool:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def add_relations_to_page(
        self, page: P, relations: R
    ) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def remove_relations_from_page(
        self, page: P, relations: R
    ) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def migrate_page(
        self, page: P, source_database_info: DatabaseInfo, destination_database_info: DatabaseInfo
    ) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def migrate_pages(
        self, pages: List[P], source_database_info: DatabaseInfo, destination_database_info: DatabaseInfo
    ) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def verify_page_migration(self, page: P) -> bool:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def migrate_all_pages(self) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )


async def _limited(semaphore: asyncio.Semaphore, coro):
    async with semaphore:
        return await coro


async def _timed(coro, page: P, label: str, debug: bool = GLOBAL_CONFIG.DEBUG) -> Any:
    if debug:
        t0 = perf_counter()
        res = await coro
        t1 = perf_counter()
        print(
            f"[TIMING] {label} page={page.Id.Id.replace('-', ''), page.Properties.Title.title} took={t1 - t0:.3f}s"
        )
    else:
        res = await coro
    return res

