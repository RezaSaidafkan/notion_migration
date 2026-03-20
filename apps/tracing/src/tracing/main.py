import logging
from asyncio import Queue
from contextlib import asynccontextmanager
from datetime import datetime
from functools import partial
from typing import Optional
from uuid import UUID
from xmlrpc.client import Boolean

import uvicorn
from common_libs.models.tracing_models import Body
from fastapi import BackgroundTasks, FastAPI, Request, Response, status
from sqlmodel import Session

from tracing.config.load_config import TRACING_CONFIG
from tracing.db.crud import (
    create_queue,
    create_session,
    get_all_from_db,
    get_by_page_id_from_db,
    get_failures_from_db,
    get_results_by_execution_id_from_db,
    setup_database,
    write_to_db,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

write_batch_to_db = partial(write_to_db, batch_size=TRACING_CONFIG.tracing_batch_size)


def get_queue(request: Request) -> Queue[Body]:
    return request.app.state.context.get("queue")


def get_session(request: Request) -> Session:
    return request.app.state.context.get("session")


@asynccontextmanager
async def lifespan(app: FastAPI):  # pylint: disable=redefined-outer-name
    engine = setup_database(TRACING_CONFIG.tracing_db_uri)
    async with \
        create_session(engine) as session, \
        create_queue(Body, TRACING_CONFIG.tracing_queue_size) as queue:
        app.state.context = {"session": session,
                             "queue": queue}
        yield

app = FastAPI(lifespan=lifespan)

@app.post("/trace_page")
async def trace_page(body: Body, request: Request, background_tasks: BackgroundTasks) -> Response:
    await get_queue(request).put(body)
    background_tasks.add_task(
        func=write_batch_to_db,
        queue=get_queue(request),
        session=get_session(request))
    return Response(status_code=status.HTTP_202_ACCEPTED)

@app.get("/get_table")
def get_table(request: Request) -> Response:
    bodies = get_all_from_db(get_session(request))
    return Response(
        status_code=status.HTTP_206_PARTIAL_CONTENT,
        content="\n".join(
            [b.model_dump_json(
                exclude={"id"}
            )
             for b in bodies]))

@app.get("/get_page_by_id")
def get_page_id(request: Request, page_id: UUID) -> Response:
    bodies = get_by_page_id_from_db(get_session(request), page_id)
    return Response(
        status_code=status.HTTP_202_ACCEPTED,
        content="\n".join(
            [b.model_dump_json(
                exclude={"outcome_exception_traceback", "id", "page_id"})
             for b in bodies]))


@app.get("/get_failures")
def get_failures(request: Request, cutoff_date: Optional[datetime] = None) -> Response:
    bodies = get_failures_from_db(get_session(request), cutoff_date)
    return Response(
        status_code=status.HTTP_202_ACCEPTED,
        content="\n".join(
            [b.model_dump_json(
                exclude={"outcome_exception_traceback", "id", "success"})
             for b in bodies]))


@app.get("/get_results_by_execution_id")
def get_results_by_execution_id(
    request: Request,
    execution_id: UUID,
    failed_only: Optional[Boolean]=False) -> Response:
    bodies = get_results_by_execution_id_from_db(get_session(request), execution_id, failed_only)
    return Response(
        status_code=status.HTTP_202_ACCEPTED,
        content="\n".join(
            [b.model_dump_json(
                exclude={"outcome_exception_traceback", "id", "execution_id"})
             for b in bodies]))

@app.get("/get_queue_state")
def get_queue_state(request: Request) -> Response:
    q_size = get_queue(request).qsize()
    return Response(str(q_size), status_code=status.HTTP_202_ACCEPTED)


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
