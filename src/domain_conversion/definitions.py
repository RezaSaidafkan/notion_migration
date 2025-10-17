import enum

class ClientJournalRelations(enum.Enum):
    ANCESTORS = "Ancestors"
    DESCENDANTS = "Descendants"
    BACKTRACK = "Backtrack"
    FORWARDTRACK = "Forwardtrack"

class ClientSourceRelations(enum.Enum):
    ANCESTORS = "Ancestors"
    DESCENDANTS = "Descendants"
    