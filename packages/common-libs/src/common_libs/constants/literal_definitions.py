# pylint: disable = invalid-name
import enum
from dataclasses import dataclass
from uuid import UUID


class JournalRelations(enum.Enum):
    ANCESTORS = "Ancestors"
    DESCENDANTS = "Descendants"
    BACKTRACK = "Backtrack"
    FORWARDTRACK = "Forwardtrack"


class SourceRelations(enum.Enum):
    ANCESTORS = "Ancestors"
    DESCENDANTS = "Descendants"
    BACKTRACK = "Backtrack"
    FORWARDTRACK = "Forwardtrack"
    JOURNALS = "Journals"


class JournalJunctionRelations(enum.Enum):
    LIFE_STYLE = "Life Style"
    NUCLEUS = "Nucleus"
    SPORTS = "Sports"
    TOUCH_DOWN = "Touchdown"
    EXCURSIONS = "Excursions"
    BELIEVES = "Believes"


class DatabaseName(enum.Enum):
    SOURCE = "Source"
    JOURNAL = "Journal"


class SourceParentPageId(enum.Enum):
    SOURCE_PARENT_PAGE = "SOURCE_PARENT_PAGE"


@dataclass
class ExecutionContext:
    PAGE_SIZE: int
    DEBUG: bool


@dataclass
class MigrationContext:
    NOTION_API_KEY: str
    SOURCE_DATASOURCE_INFO: DatasourceInfo
    TARGET_DATASOURCE_INFO: DatasourceInfo
    JOURNAL_DATASOURCE_INFO: DatasourceInfo
    JOURNAL_JUNCTION_RELATION: JournalJunctionRelations


@dataclass
class DatasourceInfo:
    DatasourceId: UUID
