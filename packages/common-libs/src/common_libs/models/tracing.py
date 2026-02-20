import time
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class Failure(BaseModel):
    exception_type: str | None
    exception_value: str
    exception_traceback: str


class Monad(BaseModel):
    success: bool
    failure: Optional[Failure] = None


class Body(BaseModel):
    page: TracePage
    trace: TracePageBody


class TracePage(BaseModel):
    id: UUID


class TracePageBody(BaseModel):
    function_name: str
    outcome: Monad
    timestamp: datetime = datetime.fromtimestamp(time.time())


class TraceSubPages(BaseModel):
    decendants: List[TraceRelation]
    function_name: str
    timestamp: datetime


class TraceRelation(BaseModel):
    page: TracePage
    outcome: Monad
