from typing import Dict

from pydantic import model_serializer
from sqlmodel import SQLModel


class Monad(SQLModel):
    success: bool
    failure: Failure | None = None

    @model_serializer
    def serialize_model(self) -> Dict[str, str | bool | None]:
        if self.failure is None:
            return {
                "success": self.success,
                "exception_type": None,
                "exception_value": None,
                "exception_traceback": None,
            }
        return {
            "success": self.success,
            "exception_type": self.failure.exception_type,
            "exception_value": self.failure.exception_value,
            "exception_traceback": self.failure.exception_traceback,
        }



class Failure(SQLModel):
    exception_type: str
    exception_value: str
    exception_traceback: str
