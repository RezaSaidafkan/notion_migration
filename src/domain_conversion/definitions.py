import enum

class ClientJournalPage(enum.Enum):
    ANCESTORS = "Ancestors"
    DESCENDANTS = "Descendants"
    BACKTRACK = "Backtrack"
    FORWARDTRACK = "Forwardtrack"