from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class TraceFilters(BaseModel):
    execution_id: Optional[UUID] = None
    cutoff_date: Optional[datetime] = None
    page_id: Optional[UUID] = None
    failed_only: Optional[bool] = None
    filtered_error_message: Optional[str] = None
    function_name: Optional[str] = None
