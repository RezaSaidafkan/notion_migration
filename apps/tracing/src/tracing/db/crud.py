import logging
from asyncio import Queue, QueueShutDown
from contextlib import asynccontextmanager
from typing import AsyncGenerator, List, Sequence

from common_libs.models.monad_models import Failure, Monad
from common_libs.models.tracing_models import TracePage
from fastapi import HTTPException, status
from sqlalchemy.engine import Engine
from sqlalchemy.exc import (
    IntegrityError,
    NoResultFound,
    OperationalError,
)
from sqlmodel import Session, SQLModel, col, create_engine, select

from tracing.db.models.table import TraceLogTable
from tracing.models.trace_filters import TraceFilters

logger = logging.getLogger()


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
