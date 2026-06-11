from abc import ABC
from dataclasses import dataclass
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

    stage_source_page_extraction_id: \
        Optional[UUID] = Field(foreign_key="stagesourcepageextractiontable.id", default=None)
    source_page_extracted: Optional["StageSourcePageExtractionTable"]\
        = Relationship(back_populates="traces")
    stage_source_page_related_pages_extracted_id: Optional[UUID]\
        = Field(foreign_key="stagesourcepagerelatedextractiontable.id", default=None)
    source_related_pages_extracted: Optional["StageSourcePageRelatedExtractionTable"]\
        = Relationship(back_populates="traces")
    stage_target_page_loaded_id: Optional[UUID] \
        = Field(foreign_key="stagetargetpageloadedtable.id", default=None)
    target_page_loaded: Optional["StageTargetPageLoadedTable"]\
        = Relationship(back_populates="traces")
    stage_target_page_relations_loaded_id: Optional[UUID]\
        = Field(foreign_key="stagetargetpagerelationsloadedtable.id", default=None)
    target_page_relations_loaded: Optional["StageTargetPageRelationsLoadedTable"] \
        = Relationship(back_populates="traces")

class ETLTable(SQLModel, table=True):
    id: UUID = Field(primary_key=True, unique=True, default_factory=uuid4)
    stage_source_page_extraction: "StageSourcePageExtractionTable" \
        = Relationship(back_populates="etl")
    stage_source_page_related_pages_extracted: Optional["StageSourcePageRelatedExtractionTable"] \
        = Relationship(back_populates="etl")
    stage_target_page_loaded: Optional["StageTargetPageLoadedTable"] \
        = Relationship(back_populates="etl")
    stage_target_page_relations_loaded: Optional["StageTargetPageRelationsLoadedTable"] \
        = Relationship(back_populates="etl")


class StageSourcePageExtractionTable(SQLModel, table=True):
    id: UUID = Field(primary_key=True)
    etl_id: Optional[UUID] = Field(foreign_key="etltable.id", default=None)
    etl: ETLTable = Relationship(back_populates="stage_source_page_extraction")

    # Foreign key for the one-to-many relationship:
    # many extraction tables can relate to one related extraction table
    related_extraction_id: Optional[UUID] = \
        Field(foreign_key="stagesourcepagerelatedextractiontable.id", default=None)
    related_page_stage: Optional["StageSourcePageRelatedExtractionTable"]\
        = Relationship(back_populates="related_pages")

    traces: List[TraceLogTable] = Relationship(back_populates="source_page_extracted")

class StageSourcePageRelatedExtractionTable(SQLModel, table=True):
    id: UUID = Field(primary_key=True)

    etl_id: Optional[UUID] = Field(foreign_key="etltable.id", default=None)
    etl: ETLTable = Relationship(back_populates="stage_source_page_related_pages_extracted")

    # One-to-many relationship: this extraction table has many related extraction tables
    related_pages: List["StageSourcePageExtractionTable"]\
        = Relationship(back_populates="related_page_stage")

    traces: List[TraceLogTable]\
        = Relationship(back_populates="source_related_pages_extracted")

class StageTargetPageLoadedTable(SQLModel, table=True):
    id: UUID = Field(primary_key=True)

    etl_id: Optional[UUID] = Field(foreign_key="etltable.id", default=None)
    etl: ETLTable = Relationship(back_populates="stage_target_page_loaded")

    stage_loaded_related_id: Optional[UUID]\
        = Field(foreign_key="stagetargetpagerelationsloadedtable.id", default=None)
    relation_stage: "StageTargetPageRelationsLoadedTable"\
        = Relationship(back_populates="loaded_related_pages")

    traces: List[TraceLogTable] = Relationship(back_populates="target_page_loaded")

class StageTargetPageRelationsLoadedTable(SQLModel, table=True):
    id: UUID = Field(primary_key=True)

    etl_id: Optional[UUID] = Field(foreign_key="etltable.id", default=None)
    etl: ETLTable = Relationship(back_populates="stage_target_page_relations_loaded")

    loaded_related_pages: Optional[List["StageTargetPageLoadedTable"]]\
        = Relationship(back_populates="relation_stage")

    traces: List[TraceLogTable] = Relationship(back_populates="target_page_relations_loaded")


@dataclass
class Stage(ABC):
    pass

@dataclass
class SourcePageExtraction(Stage):
    ...
@dataclass
class SourcePageRelatedExtraction(Stage):
    ...
@dataclass
class TargetPageLoaded(Stage):
    ...
@dataclass
class TargetPageRelationsLoaded(Stage):
    ...
