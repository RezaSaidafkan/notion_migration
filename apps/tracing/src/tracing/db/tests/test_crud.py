import asyncio
import unittest
from datetime import datetime
from uuid import UUID, uuid4

from common_libs.models.client_models import PageId
from common_libs.models.monad_models import Failure
from common_libs.models.tracing_models import (
    Monad as Outcome,
    TracePage,
    TracePageBody as Trace,
)
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel

from tracing.db.crud import (
    create_queue,
    create_session,
    get_tracing_by_filter,
    setup_database,
    add_tracing_batch,
)
from tracing.db.models.table import TraceLogTable
from tracing.models.trace_filters import TraceFilters


class TestCrud(unittest.TestCase):
    def setUp(self):
        self.engine: Engine = setup_database("sqlite:///:memory:")
        SQLModel.metadata.create_all(self.engine)
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
            trace_log = TraceLogTable(
                execution_id=self.execution_id,
                page_id=self.page_id,
                function_name="test",
                timestamp=datetime.now(),
                **Outcome(
                    success=True,
                    failure=None,
                ).model_dump(mode="python"),
            )
            session.add(trace_log)
            session.commit()
            
            tracing_filters = TraceFilters()
            
            results = get_tracing_by_filter(session, tracing_filters)
            self.assertEqual(len(results), 1)

    def test_get_by_page_id_from_db(self):
        with Session(self.engine) as session:
            trace_log = TraceLogTable(
                execution_id=self.execution_id,
                page_id=self.page_id,
                function_name="test",
                timestamp=datetime.now(),
                **Outcome(
                    success=True,
                    failure=None,
                ).model_dump(mode="python"),
            )
            session.add(trace_log)
            session.commit()
            
            tracing_filters = TraceFilters(page_id=self.page_id)
            
            results = get_tracing_by_filter(session, tracing_filters)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].page_id, self.page_id)

    def test_get_results_by_execution_id_from_db(self):
        with Session(self.engine) as session:
            trace_log = TraceLogTable(
                execution_id=self.execution_id,
                page_id=self.page_id,
                function_name="test",
                timestamp=datetime.now(),
                **Outcome(
                    success=True,
                    failure=None,
                ).model_dump(mode="python"),
            )
            session.add(trace_log)
            session.commit()
            
            tracing_filters = TraceFilters(
                execution_id=self.execution_id,
                failed_only=False
            )
            
            results = get_tracing_by_filter(session, tracing_filters)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].execution_id, self.execution_id)

    def test_get_failures_from_db(self):
        with Session(self.engine) as session:
            trace_log = TraceLogTable(
                execution_id=self.execution_id,
                page_id=self.page_id,
                function_name="test",
                timestamp=datetime.now(),
                **Outcome(
                    success=False,
                    failure=Failure(
                        exception_type="Some Error Type",
                        exception_value="Some Error Value",
                        exception_traceback="Some Error Traceback"),
                ).model_dump(mode="json")
            )
            session.add(trace_log)
            session.commit()
            
            tracing_filters = TraceFilters(
                failed_only=True
            )
            results = get_tracing_by_filter(session, tracing_filters)
            self.assertEqual(len(results), 1)
            self.assertFalse(results[0].success)
    
    def test_get_row_by_error_message(self):
        with Session(self.engine) as session:
            trace_log = TraceLogTable(
                execution_id=self.execution_id,
                page_id=self.page_id,
                function_name="test",
                timestamp=datetime.now(),
                **Outcome(
                    success=False,
                    failure=Failure(
                        exception_type="Some Error Type",
                        exception_value="Some Error Value",
                        exception_traceback="Some Error Traceback"),
                ).model_dump(mode="json"),
            )
            session.add(trace_log)
            session.commit()
            
            tracing_filters = TraceFilters(
                filtered_error_message="Some Error Value")

            results = get_tracing_by_filter(session, tracing_filters)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].success, False)

    def test_async_create_session(self):
        async def run_test():
            async with create_session(self.engine) as session:
                self.assertIsInstance(session, Session)

        asyncio.run(run_test())

    def test_async_create_queue(self):
        async def run_test():
            async with create_queue(TracePage, 1) as q:
                self.assertIsInstance(q, asyncio.Queue)

        asyncio.run(run_test())

    def test_async_write_to_db(self):
        async def run_test():
            execution_id = uuid4()
            page_id = uuid4()
            queue: asyncio.Queue[TracePage] = asyncio.Queue()
            page = PageId(Id=page_id)
            outcome = Outcome(
                success=True,
                failure=None,
            )
            trace = Trace(
                function_name="test_function",
                timestamp=datetime.now(),
                outcome=outcome,
            )
            body = TracePage(
                execution_id=execution_id,
                page_id=page,
                trace=trace,
            )
            await queue.put(body)
            
            tracing_filters = TraceFilters(
                execution_id=execution_id,
                page_id=page_id)

            with Session(self.engine) as session:
                await add_tracing_batch(session, queue, 1)
                results = get_tracing_by_filter(session, tracing_filters)
                self.assertEqual(len(results), 1)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()