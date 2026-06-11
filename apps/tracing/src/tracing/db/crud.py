import logging
from asyncio import Queue, QueueShutDown
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import singledispatch
from typing import AsyncGenerator, List, Sequence
from uuid import UUID

from common_libs.models.monad_models import Failure, Monad
from common_libs.models.tracing_models import TracePage
from fastapi import HTTPException, status
from sqlalchemy.engine import Engine
from sqlalchemy.exc import (
    IntegrityError,
    MultipleResultsFound,
    NoResultFound,
    OperationalError,
)
from sqlmodel import Session, SQLModel, col, create_engine, select

from tracing.db.models.table import (
    ETLTable,
    SourcePageExtraction,
    SourcePageRelatedExtraction,
    Stage,
    StageSourcePageExtractionTable,
    StageSourcePageRelatedExtractionTable,
    StageTargetPageLoadedTable,
    StageTargetPageRelationsLoadedTable,
    TargetPageLoaded,
    TargetPageRelationsLoaded,
    TraceLogTable,
)
from tracing.models.trace_filters import TraceFilters

logger = logging.getLogger()


@dataclass
class PageIdStage:
    source_page_id: UUID
    stage: Stage
    trace: TraceLogTable
    related_pages: Sequence[UUID]
    target_page_id: UUID | None = None

class CrudError(Exception):
    pass


@asynccontextmanager
async def create_session(engine: Engine) -> AsyncGenerator[Session]:
    with Session(engine) as session:
        try:
            yield session
        finally:
            session.close()

@asynccontextmanager
async def create_queue[T](_: T, queue_size:int) -> AsyncGenerator[Queue[T]]:
    queue = Queue[T](maxsize=queue_size)
    yield queue
    queue.shutdown()

def setup_database(db_uri: str) -> Engine:
    engine = create_engine(db_uri, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine

def get_tracing_by_filter(
    session: Session,
    filters: TraceFilters,
) -> Sequence[TraceLogTable]:
    statement = select(TraceLogTable)
    if filters.failed_only:
        # pylint: disable=singleton-comparison
        statement = statement.where(
            TraceLogTable.success == False)  # noqa: E712
    if filters.execution_id:
        statement = statement.where(
            TraceLogTable.execution_id == filters.execution_id)
    if filters.cutoff_date:
        statement = statement.where(
            TraceLogTable.timestamp >= filters.cutoff_date
        )
    if filters.page_id:
        statement = statement.where(
            TraceLogTable.page_id == filters.page_id)
    if filters.filtered_error_message:
        statement = statement.where(
            TraceLogTable.exception_value
             == filters.filtered_error_message
        )
    if filters.function_name:
        statement = statement.where(
            col(TraceLogTable.function_name).contains(filters.function_name)
        )

    try:
        return session.exec(statement).all()
    except NoResultFound:
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT) from None
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR) from None

async def add_tracing_batch(session: Session, queue: Queue[TracePage], batch_size: int):
    if queue.qsize() >= batch_size:
        batch_index = 0
        consumed_queue: List[TracePage] = []
        for _ in range(batch_index, batch_size):
            try:
                body = await queue.get()
                consumed_queue.append(body)
                outcome: Monad
                if body.trace.outcome.success:
                    outcome=Monad(
                        success=True,
                        failure=None)
                elif body.trace.outcome.failure is not None and body.trace.outcome.success is False:
                    outcome=Monad(
                        success=False,
                        failure=Failure(
                            exception_type=body.trace.outcome.failure.exception_type,
                            exception_value=body.trace.outcome.failure.exception_value,
                            exception_traceback=body.trace.outcome.failure.exception_traceback
                            )
                        )
                else:
                    raise RuntimeError("Failed outcome should have exception values")
                trace_log = TraceLogTable(
                    execution_id=body.execution_id,
                    page_id=body.page_id.Id,
                    function_name=body.trace.function_name,
                    timestamp=body.trace.timestamp,
                    **outcome.model_dump(mode="python")
                )
                session.add(trace_log)

            except (QueueShutDown, IntegrityError, OperationalError) as e:
                logger.exception(e)
                for b in consumed_queue:
                    await queue.put(b)
                session.rollback()

                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR) from None
        session.commit()
    return True


@singledispatch
async def get_etl(
    stage: Stage,
    session: Session,
    source_page_id: UUID,
    target_page_id: UUID | None = None) -> ETLTable:
    """Raise an exception for base implementation (fallback for unhandled types)."""
    raise TypeError("fallback for unhandled types")

@get_etl.register
async def _(
    stage: SourcePageExtraction | SourcePageRelatedExtraction,
    session: Session,
    source_page_id: UUID) -> ETLTable:
    statement = select(ETLTable).where(col(ETLTable.stage_source_page_extraction).
                                       has(id = source_page_id))
    try:
        result = session.exec(statement).unique().one()
        return result
    except NoResultFound:
        etl_row = ETLTable()
        source_extraction = StageSourcePageExtractionTable(id=source_page_id, etl_id=etl_row.id)
        etl_row.stage_source_page_extraction = source_extraction
        source_related_pages_extracted = StageSourcePageRelatedExtractionTable(
            id=source_page_id, etl_id=etl_row.id)
        etl_row.stage_source_page_related_pages_extracted = source_related_pages_extracted
        session.add(etl_row)
        session.add(source_extraction)
        session.add(source_related_pages_extracted)
        session.commit()

        # Refresh to ensure relationships are properly loaded
        session.refresh(etl_row)
        session.refresh(source_extraction)
        session.refresh(source_related_pages_extracted)
        return etl_row
    except MultipleResultsFound:
        raise CrudError("Found more instances of ETL. It should be unique") from None


@get_etl.register
async def _(
    stage: TargetPageLoaded | TargetPageRelationsLoaded,
    session: Session,
    source_page_id: UUID,
    target_page_id: UUID) -> ETLTable:
    etl_row = await get_etl(SourcePageExtraction(), session, source_page_id)
    if etl_row.stage_target_page_loaded is None:
        target_page_loaded = StageTargetPageLoadedTable(id=target_page_id, etl_id=etl_row.id)
        etl_row.stage_target_page_loaded = target_page_loaded
        session.add(target_page_loaded)
        session.add(etl_row)
        session.commit()
        session.refresh(etl_row)
    else:
        statement = select(ETLTable).where(
            col(ETLTable.stage_target_page_loaded).has(id = target_page_id))  # pylint: disable=no-member
        etl_row = session.exec(statement).unique().one()
    return etl_row

async def upsert_etl_queue(session: Session, queue: Queue[PageIdStage], batch_size: int):
    if queue.qsize() >= batch_size:
        batch_index = 0
        consumed_queue: List[PageIdStage] = []
        for _ in range(batch_index, batch_size):
            body = await queue.get()
            try:
                consumed_queue.append(body)
                await upsert_etl(body.stage, session, body)
            except (QueueShutDown, IntegrityError, OperationalError):
                logger.exception("Failed to upsert ETL")
                queue.put_nowait(body)
                session.rollback()
                raise CrudError("Failed to upsert ETL") from None
        session.commit()
    return True



@singledispatch
async def upsert_etl(stage: Stage,
                     session: Session,
                     page_id_stage: PageIdStage) -> None:
    _, _, _ = stage, session, page_id_stage


@upsert_etl.register
async def _(stage: SourcePageExtraction,
            session: Session,
            page_id_stage: PageIdStage):
    etl_row = await get_etl(stage, session, page_id_stage.source_page_id)
    page_id_stage.trace.stage_source_page_extraction_id = etl_row.stage_source_page_extraction.id
    session.add(page_id_stage.trace)  # is this a correct updating step?
    session.add(etl_row.stage_source_page_extraction)
    session.commit()
    session.refresh(etl_row.stage_source_page_extraction)

@upsert_etl.register
async def _(stage: SourcePageRelatedExtraction,
            session: Session,
            page_id_stage: PageIdStage):
    etl_row = await get_etl(stage, session, page_id_stage.source_page_id)
    assert etl_row.stage_source_page_related_pages_extracted is not None
    related_pages = [StageSourcePageExtractionTable(
                        id=page_id,
                        etl_id=etl_row.id,
                        related_extraction_id=etl_row.stage_source_page_related_pages_extracted.id
                        )
                     for page_id in page_id_stage.related_pages]
    page_id_stage.trace.stage_source_page_related_pages_extracted_id =\
        etl_row.stage_source_page_related_pages_extracted.id

    session.add(etl_row)
    session.add(page_id_stage.trace)
    session.add(etl_row.stage_source_page_related_pages_extracted)
    session.add_all(related_pages)
    session.commit()
    session.refresh(etl_row.stage_source_page_related_pages_extracted)
    for related_page in related_pages:
        session.refresh(related_page)

@upsert_etl.register
async def _(stage: TargetPageLoaded,
            session: Session,
            page_id_stage: PageIdStage):
    etl_row = await get_etl(
        stage,
        session,
        page_id_stage.source_page_id,
        page_id_stage.target_page_id)
    assert etl_row.stage_target_page_loaded is not None
    page_id_stage.trace.stage_target_page_loaded_id = \
        etl_row.stage_target_page_loaded.id
    session.add(etl_row)
    session.commit()
    session.refresh(etl_row.stage_target_page_loaded)

@upsert_etl.register
async def _(stage: TargetPageRelationsLoaded,
            session: Session,
            page_id_stage: PageIdStage):
    if page_id_stage.target_page_id:
        etl_row = await get_etl(
            TargetPageLoaded(),
            session,
            page_id_stage.source_page_id,
            page_id_stage.target_page_id)
        stage_target_relations = StageTargetPageRelationsLoadedTable(
            id=page_id_stage.target_page_id,
            etl_id=etl_row.id,
        )
        session.add(stage_target_relations)
        related_pages: List[StageTargetPageLoadedTable] = []
        for related_page_id in page_id_stage.related_pages:
            related_etl_row = await get_etl(
                TargetPageLoaded(),
                session,
                page_id_stage.source_page_id,
                related_page_id)
            assert related_etl_row.stage_target_page_loaded is not None
            related_etl_row.stage_target_page_loaded.stage_loaded_related_id = \
                stage_target_relations.id
            related_pages.append(related_etl_row.stage_target_page_loaded)
            session.add(related_etl_row)
            session.add(related_etl_row.stage_target_page_loaded)
        page_id_stage.trace.stage_target_page_relations_loaded_id = \
            stage_target_relations.id
        session.commit()
        session.refresh(etl_row)
        session.refresh(stage_target_relations)
        session.refresh(etl_row.stage_target_page_loaded)
        session.refresh(page_id_stage.trace)
        for related_page in related_pages:
            session.refresh(related_page)
    else:
        logger.warning("No related target pages were created for loaded page '%x'. \
            Skipping", page_id_stage.source_page_id)
