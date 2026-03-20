import time
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlmodel import SQLModel


class Body(SQLModel):
    execution_id: UUID
    page: TracePage
    trace: TracePageBody


class TracePage(SQLModel):
    id: UUID


class TracePageBody(SQLModel):
    function_name: str
    outcome: Monad
    timestamp: datetime = datetime.fromtimestamp(time.time())


class TraceRelation(SQLModel):
    page: TracePage
    # outcome: Monad  # no I don't need it, I'd only hold the foreign key


class Monad(SQLModel):
    success: bool
    failure: Optional[Failure] = None


class Failure(SQLModel):
    exception_type: str
    exception_value: str
    exception_traceback: str


class TraceSubPages(SQLModel):
    decendants: List[TraceRelation]
    # function_name: str  # no need: I'd only hold the foreign key
    # timestamp: datetime  # no need: I'd only hold the foreign key
