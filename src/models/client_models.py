from dataclasses import dataclass
from src.constants.literal_definitions import DatabaseName
from typing import List, Optional
from dataclasses_json import DataClassJsonMixin
from models.api_models import DateProperty, PeopleProperty, RichTextProperty, SelectProperty, StatusProperty, Icon, TitleProperty


@dataclass
class ClientPageProperties(DataClassJsonMixin):
    Type: Optional[SelectProperty]
    Title: Optional[TitleProperty]
    Assignee: Optional[PeopleProperty]
    Priority: Optional[SelectProperty]
    Urgency: Optional[SelectProperty]
    Status: Optional[StatusProperty]
    Timeline: Optional[DateProperty]
    Description: Optional[RichTextProperty]
    
    def __repr__(self):
        title = self.Title.__repr__() if self.Title else "<Title: None>"
        typ = self.Type.__repr__() if self.Type else "<Type: None>"
        status = self.Status.__repr__() if self.Status else "<Status: None>"
        timeline = self.Timeline.__repr__() if self.Timeline else "<Date: None>"
        return f"{title} | {typ} | {status} | {timeline}"

@dataclass
class BaseHierarchyProperty(DataClassJsonMixin):
    Ancestors: Optional[List["ClientPage"]]
    Descendants: Optional[List["ClientPage"]]
    
    def __repr__(self):
        desc_parts = []
        if self.Descendants:
            for page in self.Descendants:
                page_text = repr(page)
                desc_parts.append(indent(page_text, '\t'))

        return '\n'.join(desc_parts)

@dataclass
class ClientRelation(BaseHierarchyProperty):
    Journals: Optional[List["ClientPage"]]
    
    def __repr__(self):
        journ_parts = []
        if self.Journals:
            for page in self.Journals:
                page_text = repr(page)
                journ_parts.append(indent(page_text, '\t'))

        journ = '\n'.join(journ_parts)
        return super().__repr__() + (f"\n\tJournals:\n{journ}" if journ else "")

@dataclass
class JournalRelation(BaseHierarchyProperty):
    database = DatabaseName
    
    def __repr__(self):
        rel_parts = []
        for page in self.database:
            page_text = repr(page)
            rel_parts.append(indent(page_text, '\t'))

        rels = '\n'.join(rel_parts)
        return super().__repr__() + (f"\n\tRelations:\n{rels}" if rels else "")

@dataclass
class ClientPage(DataClassJsonMixin):
    id: str
    properties: ClientPageProperties
    relations: Optional[ClientRelation] = None
    icon: Optional[Icon] = None
    
    def __repr__(self):
        icon = self.icon.__repr__() if self.icon else ''
        rels = self.relations.__repr__() if self.relations else ''

        # ensure every line in rels is indented one more tab for the Relations: block
        rels_indented = indent(rels, '\t')
        return f"{icon} {self.properties}\n\tRelations:\n\t{rels_indented}"
    
@dataclass
class ClientJournalPage(DataClassJsonMixin):
    id: str
    properties: ClientPageProperties
    relations: Optional[JournalRelation] = None
    icon: Optional[Icon] = None
    
    def __repr__(self):
        icon = self.icon.__repr__() if self.icon else ''
        rels = self.relations.__repr__() if self.relations else ''

        # ensure every line in rels is indented one more tab for the Relations: block
        rels_indented = indent(rels, '\t')
        return f"{icon} {self.properties}\n\tRelations:\n\t{rels_indented}"

@dataclass
class JournalPageProperties(DataClassJsonMixin):
    Title: Optional[TitleProperty]
    Date: Optional[DateProperty]
    Description: Optional[RichTextProperty]
    
    def __repr__(self):
        title = self.Title.__repr__() if self.Title else "<Title: None>"
        date = self.Date.__repr__() if self.Date else "<Date: None>"
        return f"{title} | {date}"

def indent(text: str, prefix: str = '\t') -> str:
    if not text:
        return ''
    return '\n'.join(prefix + line for line in text.splitlines())