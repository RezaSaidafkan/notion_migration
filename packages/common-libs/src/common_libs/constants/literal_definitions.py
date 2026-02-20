# pylint: disable = invalid-name
import enum
from typing import Union


class JunctionRelationDefinition(enum.Enum):
    LIFE_STYLE = "Life Style"
    NUCLEUS = "Nucleus"
    SPORTS = "Sports"
    TOUCH_DOWN = "Touchdown"
    EXCURSIONS = "Excursions"
    BELIEVES = "Believes"


class JournalRelationsDefinition(enum.Enum):
    ANCESTOR = "Ancestor"
    DESCENDANTS = "Descendants"
    BACKTRACK = "Backtrack"
    FORWARDTRACK = "Forwardtrack"


class TaskRelationsDefinition(enum.Enum):
    ANCESTORS = "Ancestors"
    DESCENDANTS = "Descendants"
    BACKTRACK = "Backtrack"
    FORWARDTRACK = "Forwardtrack"
    JOURNALS = "Journals"

RelationDefinitions = Union[
    "TaskRelationsDefinition",
    "JournalRelationsDefinition",
    "JunctionRelationDefinition"]
