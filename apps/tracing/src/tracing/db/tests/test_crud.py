import asyncio
import unittest
from datetime import datetime
from uuid import UUID, uuid4

from common_libs.models.tracing_models import (
    Body,
    Monad as Outcome,
    TracePage,
    TracePageBody as Trace,
)
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel

from tracing.db.crud import (
    create_queue,
    create_session,
    get_results_from_db,
    setup_database,
    write_to_db,
)
from tracing.db.models.table import TraceLog


class TestCrud(unittest.TestCase):
    def setUp(self):
        self.engine: Engine = setup_database("sqlite:///:memory:")
        self.session: Session = Session(self.engine)
        self.page_id: UUID = uuid4()
        self.execution_id: UUID = uuid4()

    def tearDown(self):
        SQLModel.metadata.drop_all(self.engine)
        self.session.close()

    def test_setup_database(self):
        self.assertIsNotNone(self.engine)

    def test_get_all_from_db(self):
        with Session(self.engine) as session:
            trace_log = TraceLog(
                execution_id=self.execution_id,
                page_id=self.page_id,
                function_name="test",
                timestamp=datetime.now(),
                success=True,
            )
            session.add(trace_log)
            session.commit()
            results = get_results_from_db(session)
            self.assertEqual(len(results), 1)

    def test_get_by_page_id_from_db(self):
        with Session(self.engine) as session:
            trace_log = TraceLog(
                execution_id=self.execution_id,
                page_id=self.page_id,
                function_name="test",
                timestamp=datetime.now(),
                success=True,
            )
            session.add(trace_log)
            session.commit()
            results = get_results_from_db(session, page_id=self.page_id)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].page_id, self.page_id)

    def test_get_results_by_execution_id_from_db(self):
        with Session(self.engine) as session:
            trace_log = TraceLog(
                execution_id=self.execution_id,
                page_id=self.page_id,
                function_name="test",
                timestamp=datetime.now(),
                success=True,
            )
            session.add(trace_log)
            session.commit()
            results = get_results_from_db(
                session, 
                execution_id=self.execution_id,
                failed_only=False
            )
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].execution_id, self.execution_id)

    def test_get_failures_from_db(self):
        with Session(self.engine) as session:
            trace_log = TraceLog(
                execution_id=self.execution_id,
                page_id=self.page_id,
                function_name="test",
                timestamp=datetime.now(),
                success=False,
            )
            session.add(trace_log)
            session.commit()
            results = get_results_from_db(session,
                                          failed_only=True)
            self.assertEqual(len(results), 1)
            self.assertFalse(results[0].success)

    def test_async_create_session(self):
        async def run_test():
            async with create_session(self.engine) as session:
                self.assertIsInstance(session, Session)

        asyncio.run(run_test())

    def test_async_create_queue(self):
        async def run_test():
            async with create_queue(Body, 1) as q:
                self.assertIsInstance(q, asyncio.Queue)

        asyncio.run(run_test())

    def test_async_write_to_db(self):
        async def run_test():
            queue: asyncio.Queue[Body] = asyncio.Queue()
            page = TracePage(id=uuid4())
            outcome = Outcome(
                success=True,
                failure=None,
            )
            trace = Trace(
                function_name="test_function",
                timestamp=datetime.now(),
                outcome=outcome,
            )
            body = Body(
                execution_id=uuid4(),
                page=page,
                trace=trace,
            )
            await queue.put(body)

            with Session(self.engine) as session:
                await write_to_db(session, queue, 1)
                results = get_results_from_db(session)
                self.assertEqual(len(results), 1)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()