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
from sqlmodel import Session, SQLModel, select

from tracing.db.crud import (
    create_queue,
    create_session,
    get_tracing_by_filter,
    setup_database,
    add_tracing_batch,
    upsert_etl,
    upsert_etl_queue,
    get_etl,
    PageIdStage,
)
from tracing.db.models.table import TraceLogTable
from tracing.db.models.table import (
    ETLTable,
    SourcePageExtraction,
    SourcePageRelatedExtraction,
    StageTargetPageLoadedTable,
    StageTargetPageRelationsLoadedTable,
    StageSourcePageRelatedExtractionTable,
    # SourcePageTable,
    Stage,
    TargetPageLoaded,
    StageSourcePageExtractionTable,
    TargetPageRelationsLoaded,
    #TargetPageTable,
    TraceLogTable,
)
from tracing.models.trace_filters import TraceFilters


class TestTraceTableCrud(unittest.TestCase):
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
                stage=SourcePageExtraction(),
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


class TestEtlCrud(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine: Engine = setup_database("sqlite:///:memory:")
        self.session: Session = Session(self.engine)
        SQLModel.metadata.create_all(self.engine)
    
    def tearDown(self):
        SQLModel.metadata.drop_all(self.engine)
        self.session.close()
    
    def test_setup_database(self):
        self.assertIsNotNone(self.engine)

    async def test_upsert_etl_stage_source_page_extracted_page_single_trace(self):
        # Arrange
        stage = SourcePageExtraction()
        page_id = uuid4()
        trace = TraceLogTable(
                execution_id=uuid4(),
                page_id=page_id,
                function_name="test",
                timestamp=datetime.now(),
                success=True,
                exception_type=None,
                exception_value=None,
                exception_traceback=None,
                )
        page_id_stage = PageIdStage(
            source_page_id=page_id,
            target_page_id=None,
            stage=stage,
            trace=trace,
            related_pages=[]
        )

        with Session(self.engine) as session:
            session.add(trace)
            session.commit()

            # Act
            await upsert_etl(stage, session, page_id_stage)
            
            # Assert
            etl_row = await get_etl(stage, session, page_id_stage.source_page_id)
            self.assertIsNotNone(etl_row)
            self.assertIsNotNone(etl_row.stage_source_page_extraction)
            self.assertIsNotNone(etl_row.stage_source_page_related_pages_extracted)
            self.assertEqual(len(etl_row.stage_source_page_extraction.traces), 1)
            self.assertEqual(etl_row.stage_source_page_extraction.traces[0], trace)

    async def test_upsert_etl_stage_source_page_extracted_page_multiple_traces(self):
        # Arrange
        stage = SourcePageExtraction()
        page_id = uuid4()
        trace1 = TraceLogTable(
                execution_id=uuid4(),
                page_id=page_id,
                function_name="test_1",
                timestamp=datetime.now(),
                success=True,
                exception_type=None,
                exception_value=None,
                exception_traceback=None,
                )
        trace2 = TraceLogTable(
                execution_id=uuid4(),
                page_id=page_id,
                function_name="test_2",
                timestamp=datetime.now(),
                success=True,
                exception_type=None,
                exception_value=None,
                exception_traceback=None,
                )
        page_id_stage_1 = PageIdStage(
            source_page_id=page_id,
            target_page_id=None,
            stage=stage,
            trace=trace1,
            related_pages=[]
        )
        page_id_stage_2 = PageIdStage(
            source_page_id=page_id,
            target_page_id=None,
            stage=stage,
            trace=trace2,
            related_pages=[]
        )
        with Session(self.engine) as session:
            session.add_all([trace1, trace2])
            session.commit()

            # Act
            await upsert_etl(stage, session, page_id_stage_1)
            await upsert_etl(stage, session, page_id_stage_2)
            
            # Assert
            etl_row = await get_etl(stage, session, page_id_stage_1.source_page_id)
            self.assertIsNotNone(etl_row)
            self.assertIsNotNone(etl_row.stage_source_page_extraction)
            self.assertEqual(len(etl_row.stage_source_page_extraction.traces), 2)
            self.assertEqual(etl_row.stage_source_page_extraction.traces, [trace1, trace2])

    async def test_upsert_etl_stage_source_extracted_related_pages(self):
        # Arrange
        stage = SourcePageRelatedExtraction()
        page_id = uuid4()
        related_page_1_id = uuid4()
        related_page_2_id = uuid4()

        trace = TraceLogTable(
                execution_id=uuid4(),
                page_id=page_id,
                function_name="test_1",
                timestamp=datetime.now(),
                success=True,
                exception_type=None,
                exception_value=None,
                exception_traceback=None,
                )
        page_id_stage = PageIdStage(
            source_page_id=page_id,
            target_page_id=None,
            stage=stage,
            trace=trace,
            related_pages=[related_page_1_id, related_page_2_id]
        )

        with Session(self.engine) as session:
            session.add(trace)
            session.commit()
            
            # Act
            await upsert_etl(stage, session, page_id_stage)
            
            # Assert
            etl_row = await get_etl(stage, session, page_id_stage.source_page_id)
            self.assertIsNotNone(etl_row)
            self.assertIsNotNone(etl_row.stage_source_page_extraction)
            self.assertIsNotNone(etl_row.stage_source_page_related_pages_extracted)
            self.assertEqual(len(etl_row.stage_source_page_related_pages_extracted.related_pages), 2)
            self.assertEqual(etl_row.stage_source_page_related_pages_extracted.related_pages[0].id, related_page_1_id)
            self.assertEqual(etl_row.stage_source_page_related_pages_extracted.related_pages[1].id, related_page_2_id)
        
    async def test_upsert_etl_stage_target_page_loaded(self):
        # Arrange
        stage = TargetPageLoaded()
        source_page_id = uuid4()
        target_page_id = uuid4()
        trace = TraceLogTable(
                execution_id=uuid4(),
                page_id=source_page_id,
                function_name="test_1",
                timestamp=datetime.now(),
                success=True,
                exception_type=None,
                exception_value=None,
                exception_traceback=None,
                )
        
        page_id_stage = PageIdStage(
            source_page_id=source_page_id,
            target_page_id=target_page_id,
            stage=stage,
            trace=trace,
            related_pages=[]
        )

        with Session(self.engine) as session:
            session.add(trace)
            session.commit()
            
            # Act
            await upsert_etl(stage, session, page_id_stage)
            
            # Assert
            etl_row = await get_etl(stage, session, page_id_stage.source_page_id, page_id_stage.target_page_id)
            self.assertIsNotNone(etl_row)
            self.assertIsNotNone(etl_row.stage_target_page_loaded)
            self.assertEqual(etl_row.stage_target_page_loaded.id, target_page_id)
            self.assertEqual(len(etl_row.stage_target_page_loaded.traces), 1)
            self.assertEqual(etl_row.stage_target_page_loaded.traces[0], trace)
        
    async def test_upsert_etl_stage_single_target_relation_loaded(self):
        # Arrange
        source_stage = SourcePageExtraction()
        target_stage = TargetPageLoaded()
        target_relation_stage = TargetPageRelationsLoaded()

        source_page_1_id = uuid4()
        source_page_2_id = uuid4()
        target_page_1_id = uuid4()
        target_page_2_id = uuid4()

        trace_1 = TraceLogTable(
                execution_id=uuid4(),
                page_id=source_page_1_id,
                function_name="test_1",
                timestamp=datetime.now(),
                success=True,
                exception_type=None,
                exception_value=None,
                exception_traceback=None,
                )
        trace_2 = TraceLogTable(
                execution_id=uuid4(),
                page_id=source_page_2_id,
                function_name="test_2",
                timestamp=datetime.now(),
                success=True,
                exception_type=None,
                exception_value=None,
                exception_traceback=None,
                )
        
        trace_3 = TraceLogTable(
                execution_id=uuid4(),
                page_id=target_page_1_id,
                function_name="test_3",
                timestamp=datetime.now(),
                success=True,
                exception_type=None,
                exception_value=None,
                exception_traceback=None,
                )
        trace_4 = TraceLogTable(
                execution_id=uuid4(),
                page_id=target_page_2_id,
                function_name="test_4",
                timestamp=datetime.now(),
                success=True,
                exception_type=None,
                exception_value=None,
                exception_traceback=None,
                )
        
        source_page_1_id_stage = PageIdStage(
            source_page_id=source_page_1_id,
            target_page_id=target_page_1_id,
            stage=source_stage,
            trace=trace_1,
            related_pages=[]
        )
        source_page_2_id_stage = PageIdStage(
            source_page_id=source_page_2_id,
            target_page_id=target_page_2_id,
            stage=source_stage,
            trace=trace_2,
            related_pages=[source_page_1_id]
        )
        
        target_page_1_id_stage = PageIdStage(
            source_page_id=source_page_1_id,
            target_page_id=target_page_1_id,
            stage=target_stage,
            trace=trace_3,
            related_pages=[]
        )
        
        target_page_2_id_stage = PageIdStage(
            source_page_id=source_page_2_id,
            target_page_id=target_page_2_id,
            stage=target_relation_stage,
            trace=trace_4,
            related_pages=[target_page_1_id]
        )

        with Session(self.engine) as session:
            session.add_all([trace_1, trace_2, trace_3, trace_4])
            session.commit()
            await upsert_etl(source_stage, session, source_page_1_id_stage)
            await upsert_etl(source_stage, session, source_page_2_id_stage)
            await upsert_etl(target_stage, session, target_page_1_id_stage)

            # Act
            await upsert_etl(target_relation_stage, session, target_page_2_id_stage)
            
            # Assert
            etl_row = await get_etl(target_relation_stage, session, target_page_2_id_stage.source_page_id, target_page_2_id_stage.target_page_id)
            self.assertIsNotNone(etl_row)
            self.assertIsNotNone(etl_row.stage_target_page_relations_loaded)
            self.assertEqual(len(etl_row.stage_target_page_relations_loaded.loaded_related_pages), 1)
            self.assertEqual(etl_row.stage_target_page_relations_loaded.loaded_related_pages[0].id, target_page_1_id)
            self.assertEqual(len(etl_row.stage_target_page_relations_loaded.traces), 1)
            self.assertEqual(etl_row.stage_target_page_relations_loaded.traces[0], trace_4)
    
    
    async def test_upsert_etl_stage_multiple_target_relation_loaded(self):
        # Arrange
        source_stage = SourcePageExtraction()
        target_stage = TargetPageLoaded()
        target_relation_stage = TargetPageRelationsLoaded()

        source_page_1_id = uuid4()
        source_page_2_id = uuid4()
        source_page_3_id = uuid4()
        target_page_1_id = uuid4()
        target_page_2_id = uuid4()
        target_page_3_id = uuid4()

        trace_1 = TraceLogTable(
                execution_id=uuid4(),
                page_id=source_page_1_id,
                function_name="test_1",
                timestamp=datetime.now(),
                success=True,
                exception_type=None,
                exception_value=None,
                exception_traceback=None,
                )
        trace_2 = TraceLogTable(
                execution_id=uuid4(),
                page_id=source_page_2_id,
                function_name="test_2",
                timestamp=datetime.now(),
                success=True,
                exception_type=None,
                exception_value=None,
                exception_traceback=None,
                )
        
        trace_3 = TraceLogTable(
                execution_id=uuid4(),
                page_id=target_page_1_id,
                function_name="test_3",
                timestamp=datetime.now(),
                success=True,
                exception_type=None,
                exception_value=None,
                exception_traceback=None,
                )
        trace_4 = TraceLogTable(
                execution_id=uuid4(),
                page_id=target_page_2_id,
                function_name="test_4",
                timestamp=datetime.now(),
                success=True,
                exception_type=None,
                exception_value=None,
                exception_traceback=None,
                )
        trace_5 = TraceLogTable(
                execution_id=uuid4(),
                page_id=target_page_3_id,
                function_name="test_5",
                timestamp=datetime.now(),
                success=True,
                exception_type=None,
                exception_value=None,
                exception_traceback=None,
                )
        trace_6 = TraceLogTable(
                execution_id=uuid4(),
                page_id=target_page_3_id,
                function_name="test_6",
                timestamp=datetime.now(),
                success=True,
                exception_type=None,
                exception_value=None,
                exception_traceback=None,
                )
        
        source_page_1_id_stage = PageIdStage(
            source_page_id=source_page_1_id,
            stage=source_stage,
            trace=trace_1,
            related_pages=[]
        )
        source_page_2_id_stage = PageIdStage(
            source_page_id=source_page_2_id,
            stage=source_stage,
            trace=trace_2,
            related_pages=[]
        )
        source_page_3_id_stage = PageIdStage(
            source_page_id=source_page_3_id,
            target_page_id=target_page_3_id,
            stage=source_stage,
            trace=trace_3,
            related_pages=[source_page_1_id, source_page_2_id]
        )
        
        target_page_1_id_stage = PageIdStage(
            source_page_id=source_page_1_id,
            target_page_id=target_page_1_id,
            stage=target_stage,
            trace=trace_4,
            related_pages=[]
        )
        
        target_page_2_id_stage = PageIdStage(
            source_page_id=source_page_2_id,
            target_page_id=target_page_2_id,
            stage=target_relation_stage,
            trace=trace_5,
            related_pages=[]
        )
        
        target_page_3_id_stage = PageIdStage(
            source_page_id=source_page_3_id,
            target_page_id=target_page_3_id,
            stage=target_relation_stage,
            trace=trace_6,
            related_pages=[target_page_1_id, target_page_2_id]
        )

        with Session(self.engine) as session:
            session.add_all([trace_1, trace_2, trace_3, trace_4, trace_5, trace_6])
            session.commit()
            await upsert_etl(source_stage, session, source_page_1_id_stage)
            await upsert_etl(source_stage, session, source_page_2_id_stage)
            await upsert_etl(source_stage, session, source_page_3_id_stage)
            await upsert_etl(target_stage, session, target_page_1_id_stage)
            await upsert_etl(target_stage, session, target_page_2_id_stage)

            # Act
            await upsert_etl(target_relation_stage, session, target_page_3_id_stage)
            
            # Assert
            etl_row = await get_etl(target_relation_stage, session, target_page_3_id_stage.source_page_id, target_page_3_id_stage.target_page_id)
            self.assertIsNotNone(etl_row)
            self.assertIsNotNone(etl_row.stage_target_page_relations_loaded)
            self.assertEqual(len(etl_row.stage_target_page_relations_loaded.loaded_related_pages), 2)
            self.assertEqual(etl_row.stage_target_page_relations_loaded.loaded_related_pages[0].id, target_page_1_id)
            self.assertEqual(etl_row.stage_target_page_relations_loaded.loaded_related_pages[1].id, target_page_2_id)
            self.assertEqual(len(etl_row.stage_target_page_relations_loaded.traces), 1)
            self.assertEqual(etl_row.stage_target_page_relations_loaded.traces[0], trace_6)

        
if __name__ == "__main__":
    unittest.main()