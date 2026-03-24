import logging
from asyncio import Queue, QueueShutDown
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, List, Optional, Sequence
from uuid import UUID
from xmlrpc.client import Boolean

from common_libs.models.tracing_models import Body
from fastapi import HTTPException, status
from sqlalchemy.engine import Engine
from sqlalchemy.exc import (
    IntegrityError,
    NoResultFound,
    OperationalError,
)
from sqlmodel import Session, SQLModel, create_engine, select

from tracing.db.models.table import TraceLog

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


def get_results_from_db(
    session: Session,
    execution_id: Optional[UUID] = None,
    cutoff_date: Optional[datetime] = None,
    page_id: Optional[UUID] = None,
    failed_only: Optional[Boolean] = None) -> Sequence[TraceLog]:
    statement = select(TraceLog)
    if failed_only:
        # pylint: disable=singleton-comparison
        statement = statement.where(
            TraceLog.success == False)  # noqa: E712
    if execution_id:
        statement = statement.where(
            TraceLog.execution_id == execution_id)
    if cutoff_date:
        statement = statement.where(
            TraceLog.timestamp >= cutoff_date
        )
    if page_id:
        statement = statement.where(
            TraceLog.page_id==page_id)

    try:
        return session.exec(statement).all()
    except NoResultFound:
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT) from None
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR) from None


async def write_to_db(session: Session, queue: Queue[Body], batch_size: int):
    if queue.qsize() >= batch_size:
        batch_index = 0
        consumed_queue: List[Body] = []
        for _ in range(batch_index, batch_size):
            try:
                body = await queue.get()
                consumed_queue.append(body)
                trace_log = TraceLog(
                    execution_id=body.execution_id,
                    page_id=body.page.id,
                    function_name=body.trace.function_name,
                    timestamp=body.trace.timestamp,
                    success=body.trace.outcome.success,
                    outcome_exception_value=None,
                    outcome_exception_traceback=None,
                    outcome_exception_type=None
                    )
                if body.trace.outcome.failure is not None:
                    trace_log.outcome_exception_value=\
                        body.trace.outcome.failure.exception_value
                    trace_log.outcome_exception_traceback=\
                        body.trace.outcome.failure.exception_traceback
                    trace_log.outcome_exception_type=\
                        body.trace.outcome.failure.exception_type
                session.add(trace_log)

            except (QueueShutDown, IntegrityError, OperationalError) as e:
                logger.exception(e)
                for b in consumed_queue:
                    await queue.put(b)
                session.rollback()

                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR) from None
        session.commit()
    return True
