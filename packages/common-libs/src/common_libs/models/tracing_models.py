import time
from datetime import datetime
from uuid import UUID

from sqlmodel import SQLModel
from tracing.db.models.table import Stage

from common_libs.models.client_models import PageId
from common_libs.models.monad_models import Monad


class TracePage(SQLModel):
    execution_id: UUID
    page_id: PageId
    trace: TracePageBody
    stage: Stage


class TracePageBody(SQLModel):
    function_name: str
    outcome: Monad
    timestamp: datetime = datetime.fromtimestamp(time.time())
