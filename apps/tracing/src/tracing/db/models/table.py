from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class TraceLog(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    execution_id: UUID
    page_id: UUID
    function_name: str
    timestamp: datetime
    success: bool
    outcome_exception_type: Optional[str]
    outcome_exception_value: Optional[str]
    outcome_exception_traceback: Optional[str]
