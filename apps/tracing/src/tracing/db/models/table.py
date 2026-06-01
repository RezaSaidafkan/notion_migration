from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel


class TraceLogTable(SQLModel, table=True):
    execution_id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)
    page_id: UUID
    function_name: str
    timestamp: datetime
    success: bool
    exception_type: Optional[str] = None
    exception_value: Optional[str] = None
    exception_traceback: Optional[str] = None

    source_page_extracted: Optional["SourcePageExtractionTable"] = \
        Relationship(back_populates="traces")
    source_page_related_extracted_pages: Optional[List["SourceRelatedPageExtractionTable"]] = \
        Relationship(back_populates="traces")
    loaded_target_page: Optional["LoadedTargetPageTable"] = \
        Relationship(back_populates="traces")
    loaded_relations: Optional[List["LoadedRelationsTable"]] = \
        Relationship(back_populates="traces")

class ETLTable(SQLModel, table=True):
    id: UUID = Field(primary_key=True, unique=True)
    source_page: Optional[SourcePageIdTable] = Relationship(back_populates="elt")
    target_page: Optional[TargetPageIdTable] = Relationship(back_populates="elt")

class SourcePageIdTable(SQLModel, table=True):
    id: UUID = Field(primary_key=True, unique=True)
    etl_id: UUID = Field(foreign_key="etltable.id")

    elt: ETLTable = Relationship(back_populates="source_page")
    extracted_source_page: Optional[List["SourcePageExtractionTable"]] = \
        Relationship(back_populates="page")
    extracted_source_related_pages: Optional[List["SourceRelatedPageExtractionTable"]] = \
        Relationship()


class TargetPageIdTable(SQLModel, table=True):
    id: UUID = Field(primary_key=True, unique=True)
    etl_id: UUID = Field(foreign_key="etltable.id")

    elt: ETLTable = Relationship(back_populates="target_page")
    loaded_target_page: Optional["LoadedTargetPageTable"] = \
        Relationship(back_populates="page")
    loaded_relations: Optional[List["LoadedRelationsTable"]] = \
        Relationship(back_populates="relations")

class SourcePageExtractionTable(SQLModel, table=True):
    id: UUID = Field(primary_key=True)
    page_id: UUID = Field(foreign_key="sourcepageidtable.id")
    trace_id: UUID = Field(foreign_key="tracelogtable.execution_id")

    page: Optional[SourcePageIdTable] = Relationship(back_populates="extracted_source_page")
    traces: List[TraceLogTable] = Relationship(back_populates="source_page_extracted")

class SourceRelatedPageExtractionTable(SQLModel, table=True):
    id: UUID = Field(primary_key=True)
    page_id: UUID = Field(foreign_key="sourcepageidtable.id")
    trace_id: UUID = Field(foreign_key="tracelogtable.execution_id")

    pages: List[SourcePageIdTable] = Relationship(back_populates="extracted_source_related_pages")
    traces: List[TraceLogTable] = Relationship(back_populates="source_page_related_extracted_pages")

class LoadedTargetPageTable(SQLModel, table=True):
    id: UUID = Field(primary_key=True)
    page_id: UUID = Field(foreign_key="targetpageidtable.id")
    trace_id: UUID = Field(foreign_key="tracelogtable.execution_id")

    page: Optional[TargetPageIdTable] = Relationship(back_populates="loaded_target_page")
    traces: List[TraceLogTable] = Relationship(back_populates="loaded_target_page")

class LoadedRelationsTable(SQLModel, table=True):
    id: UUID = Field(primary_key=True)
    page_ids: UUID = Field(foreign_key="targetpageidtable.id")
    trace_id: UUID = Field(foreign_key="tracelogtable.execution_id")

    relations: Optional[List[TargetPageIdTable]] = Relationship(back_populates="loaded_relations")
    traces: List[TraceLogTable] = Relationship(back_populates="loaded_relations")
##
# class RelationSet(SQLModel):
#     id: PageId = Field(primary_key=True)
#     target_page_id: PageId
#     outcome: Monad

# class Loaded(SQLModel):
#     id: PageId = Field(primary_key=True)
#     outcome: Monad
#     target_page_id: PageId

# class Extracted(SQLModel):
#     id: PageId = Field(primary_key=True)
#     outcome: Monad

# class ExtractedSubpages(SQLModel):
#     id: PageId = Field(primary_key=True)
#     outcome: Monad
#     sub_pages: Sequence[PageId]

# class RelationsSet(SQLModel):
#     id: PageId = Field(primary_key=True)
#     outcome: Monad
#     relations_set: Sequence[RelationSet]

# type EtlBody = Extracted | ExtractedSubpages | Loaded | RelationsSet

# class Monad(SQLModel):
#     success: bool
#     failure: Optional[Failure] = None

# class Failure(SQLModel):
#     exception_type: str
#     exception_value: str
#     exception_traceback: str

# class TracePage(SQLModel):
#     execution_id: UUID
#     page_id: PageId
#     trace: TracePageBody

# class TracePageBody(SQLModel):
#     function_name: str
#     outcome: Monad
#     timestamp: datetime = datetime.fromtimestamp(time.time())
