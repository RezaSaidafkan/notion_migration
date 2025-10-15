#!/usr/bin/env python3
import enum

class DatabaseName(enum.Enum):
    LIFE_STYLE = "Life Style"
    NUCLEUS = "Nucleus"
    SPORTS = "Sports"
    TOUCH_DOWN = "Touchdown"
    EXCURSIONS = "Excursions"
    BELIEVES = "Believes"
    JOURNAL = "Journal"
    
class JournalName(enum.Enum):
    JOURNAL = "Journal"

class SourceParentPageId(enum.Enum):
    SOURCE_PARENT_PAGE = "SOURCE_PARENT_PAGE"