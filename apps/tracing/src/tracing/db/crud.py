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


def get_all_from_db(session: Session) -> Sequence[TraceLog]:
    statement = select(TraceLog)
    try:
        return session.exec(statement).all()
    except NoResultFound:
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT) from None
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR) from None

def get_by_page_id_from_db(session: Session, page_id: UUID) -> Sequence[TraceLog]:
    statement = select(TraceLog).where(TraceLog.page_id==page_id)
    try:
        return session.exec(statement).all()
    except NoResultFound:
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT) from None
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR) from None

def get_results_by_execution_id_from_db(
    session: Session,
    execution_id: UUID,
    failed_only: Optional[Boolean]) -> Sequence[TraceLog]:
    if failed_only:
        statement = select(TraceLog).where(
            not TraceLog.success,
            TraceLog.execution_id==execution_id)
    else:
        statement = select(TraceLog).where(TraceLog.execution_id==execution_id)
    try:
        return session.exec(statement).all()
    except NoResultFound:
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT) from None
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR) from None


def get_failures_from_db(session: Session, cutoff_date: Optional[datetime]) -> Sequence[TraceLog]:
    if cutoff_date:
        statement = select(TraceLog).where(
            not TraceLog.success, TraceLog.timestamp >= cutoff_date
        )
    else:
        statement = select(TraceLog).where(not TraceLog.success)
    try:
        return session.exec(statement).all()
    except NoResultFound as e:
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT) from e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR) from e


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
