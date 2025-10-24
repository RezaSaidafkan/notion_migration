#!/usr/bin/env python3
from dataclasses import dataclass
import enum


class JournalRelations(enum.Enum):
    ANCESTORS = "Ancestors"
    DESCENDANTS = "Descendants"
    BACKTRACK = "Backtrack"
    FORWARDTRACK = "Forwardtrack"
    LIFE_STYLE = "Life Style"
    NUCLEUS = "Nucleus"
    SPORTS = "Sports"
    TOUCH_DOWN = "Touchdown"
    EXCURSIONS = "Excursions"
    BELIEVES = "Believes"


class SourceRelations(enum.Enum):
    ANCESTORS = "Ancestors"
    DESCENDANTS = "Descendants"
    BACKTRACK = "Backtrack"
    FORWARDTRACK = "Forwardtrack"
    JOURNALS = "Journals"


class DatabaseName(enum.Enum):
    SOURCE = "Source"
    JOURNAL = "Journal"


class SourceParentPageId(enum.Enum):
    SOURCE_PARENT_PAGE = "SOURCE_PARENT_PAGE"


PAGINATION_SIZE = 20


@dataclass
class DatabaseInfo:
    DatabaseId: str
