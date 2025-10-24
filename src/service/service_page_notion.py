from typing import List, Union, Any, Type, cast
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
    CommonPage,
    PageRelation,
    JournalRelation,
    PageId,
    T,
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


class ServicePage(ServicePageInterface[T]):
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

    async def refresh_from_backend(self, page_id: PageId) -> CommonPage:
        retrieved_page = await self._repo_source.read_page(page_id)
        return Page(
            Id=page_id, Icon=retrieved_page.Icon, Properties=retrieved_page.Properties
        )

    def get_pages(
        self,
        page: T,
        database_info: DatabaseInfo,
        relation: Union[SourceRelations, JournalRelations],
        tg: asyncio.TaskGroup,
    ) -> Task[List[T]]:
        return tg.create_task(
            _timed(
                self.query_database(
                    database_info=database_info,
                    database_type=type(page),
                    filter={
                        "property": relation.value,
                        "relation": {"contains": page.Id.Id},
                    },
                ),
                page,
                "query_database:sub_pages",
            ),
        )

    async def query_database(
        self, database_info: DatabaseInfo, database_type: Type[T], filter: dict
    ) -> List[T]:
        print("database_type: ", database_type)
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
        pages: List[T] = []

        while not exhausted:
            # The cast is safe because of the if/elif block above.
            pagination = await repo.query_database(
                database_id=database_info.DatabaseId,
                page_size=GLOBAL_CONFIG.PAGE_SIZE,
                filter=filter,
                cursor=cursor,
            )

            pages.extend(cast(List[T], pagination.results))
            cursor = pagination.next_cursor
            exhausted = not pagination.has_more
        return pages

    async def build_page_hierarchy(
        self,
        root_page: T,
        source_database: DatabaseInfo,
        journal_database: DatabaseInfo,
        journal_relation: JournalRelations,
        level: int = 0,
    ) -> List[T]:
        """
        Return pages whose 'Ancestor' relation contains the given parent.

        This method contains the schema knowledge ('Ancestor' relation) and
        delegates to the repository's generic `query_database` method.
        """
        collected: list[T] = []

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
        page: T,
        source_database: DatabaseInfo,
        journal_database: DatabaseInfo,
        journal_relation: JournalRelations,
        level: int,
        collected: list[T],
        tg: asyncio.TaskGroup,
        semaphore: asyncio.Semaphore,
    ):
        # create the coroutines and run them concurrently with timing

        sub_pages_tasks: Task[List[T]] = self.get_pages(
            page=page,
            database_info=source_database,
            relation=SourceRelations.JOURNALS,
            tg=tg,
        )

        journal_database_tasks: Task[List[T]] = self.get_pages(
            page=page, database_info=journal_database, relation=journal_relation, tg=tg
        )

        sub_pages, journal_database_pages = await asyncio.gather(
            sub_pages_tasks, journal_database_tasks
        )
        page.Relations = PageRelation(Descendants=None, Ancestors=None, Journals=None)

        if journal_database_pages is not None:
            # page.Relations.Journals = cast(List[JournalPage], journal_database_pages)
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

        if sub_pages is not None:
            # page.Relations.Descendants = cast(List[CommonPage], sub_pages)
            page.Relations.Descendants = sub_pages
            for sub_page in sub_pages:
                tg.create_task(
                    _timed(
                        _limited(
                            semaphore,
                            self.process_source_recursive(
                                sub_page,
                                source_database,
                                journal_database,
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
        page: T,
        journal_database_info: DatabaseInfo,
        journal_relation: JournalRelations,
        tg: asyncio.TaskGroup,
        semaphore: asyncio.Semaphore,
    ):
        """
        This function processes a journal page recursively, fetching its sub-journal pages.
        Assigns the found sub-journal pages to the Relations.Descendants / Relations.Ancestors attributes of the page.
        """
        sub_journal_pages: List[T] = await self.query_database(
            database_info=journal_database_info,
            database_type=type(page),
            filter={
                "property": journal_relation.DESCENDANTS.value,
                "relation": {"contains": page.Id},
            },
        )

        if sub_journal_pages:
            page.Relations = JournalRelation(
                Descendants=cast(List[T], sub_journal_pages),
                Ancestors=cast(List[T], [page]),
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

    async def create_or_update_page(self, page: CommonPage) -> CommonPage:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def add_relations_to_page(
        self, page: CommonPage, relations: List[str]
    ) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def remove_relations_from_page(
        self, page: CommonPage, relations: List[str]
    ) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def migrate_page(
        self, page: CommonPage, sourceDatabaseId: str, destinationDatabaseId: str
    ) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def migrate_pages(
        self, pages: List[CommonPage], sourceDatabaseId: str, destinationDatabaseId: str
    ) -> None:
        raise NotImplementedError(
            "This method should be implemented in the service layer."
        )

    async def verify_page_migration(self, page: CommonPage) -> bool:
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


async def _timed(coro, page: T, label: str, debug: bool = GLOBAL_CONFIG.DEBUG) -> Any:
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
