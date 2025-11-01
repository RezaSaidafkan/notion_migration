from dataclasses import dataclass
from src.constants.literal_definitions import JournalRelations
from typing import List, Optional, Union, TypeVar, Generic
from dataclasses_json import DataClassJsonMixin
from .api_models import (
    DateProperty,
    PeopleProperty,
    RichTextProperty,
    SelectProperty,
    StatusProperty,
    IconProperty,
    TitleProperty,
)

# Define P as Page types
P = TypeVar("P", bound=Union["Page", "JournalPage"])
# P = TypeVar("P", Page, JournalPage)
# Define DB as Database types
DB = TypeVar("DB", bound=Union["Page", "JournalPage"])
# Define R as Relation types
R = TypeVar("R", bound=Union["PageRelation", "JournalRelation"])
# Define K as Page ID type
K = TypeVar("K", bound="PageId")


@dataclass
class PageId(DataClassJsonMixin):
    Id: str


@dataclass
class PageProperties(DataClassJsonMixin):
    Title: TitleProperty
    Type: Optional[SelectProperty]
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
class JournalPageProperties(DataClassJsonMixin):
    Title: TitleProperty
    Type: Optional[SelectProperty]
    Status: Optional[SelectProperty]  # update in the database, now we have State in source db and Select in journal db
    Timeline: Optional[DateProperty]
    Description: Optional[RichTextProperty]

    def __repr__(self):
        title = self.Title.__repr__() if self.Title else "<Title: None>"
        typ = self.Type.__repr__() if self.Type else "<Type: None>"
        status = self.Status.__repr__() if self.Status else "<Status: None>"
        timeline = self.Timeline.__repr__() if self.Timeline else "<Date: None>"
        return f"{title} | {typ} | {status} | {timeline}"


@dataclass
class BaseHierarchyProperty(Generic[P], DataClassJsonMixin):
    Ancestors: Optional[List["P"]]
    Descendants: Optional[List["P"]]

    def __repr__(self):
        rel_parts = []
        if self.Descendants:
            for page in self.Descendants:
                page_text = repr(page)
                rel_parts.append(indent(page_text, "\t"))
        
        if rel_parts:
            return format_relation_heirarchy(
                "", "\n".join(rel_parts), "Descendants"
            )
        return ""


@dataclass
class PageRelation(Generic[P], BaseHierarchyProperty[P]):
    Journals: Optional[List["P"]]

    def __repr__(self):
        journ_parts = []
        if self.Journals:
            for page in self.Journals:
                page_text = repr(page)
                journ_parts.append(indent(page_text, "\t"))
        
        base_repr = super().__repr__()
        if journ_parts:
            journ = "\n".join(journ_parts)
            return format_relation_heirarchy(base_repr, journ, "Journals")
        return base_repr

@dataclass
class JournalRelation(BaseHierarchyProperty):
    Database: Optional[JournalRelations] = None
    Backtrack: Optional[List["JournalPage"]] = None  # Ancestors
    Forwardtrack: Optional[List["JournalPage"]] = None  # Descendants

    def __repr__(self):
        rel_parts = []
        if self.Database:
            rel_parts.append(indent(self.Database, "\t"))
        if self.Backtrack:
            for page in self.Backtrack:
                page_text = repr(page)
                rel_parts.append(indent(page_text, "\t"))
        if self.Forwardtrack:
            for page in self.Forwardtrack:
                page_text = repr(page)
                rel_parts.append(indent(page_text, "\t"))

        base_repr = super().__repr__()
        if rel_parts:
            rels = "\n".join(rel_parts)
            return format_relation_heirarchy(base_repr, rels, "Database")
        return base_repr


@dataclass
class CommonPage(DataClassJsonMixin):
    Id: PageId
    Properties: Union[PageProperties, JournalPageProperties]
    Icon: Optional[IconProperty]

    def __repr__(self):
        icon = self.Icon.__repr__() if self.Icon else ""
        return f"{icon} {self.Properties}"


@dataclass
class Page(CommonPage):
    Relations: Optional[PageRelation] = None

    def __repr__(self):
        # ensure every line in rels is indented one more tab for the Relations: block
        return format_relation_heirarchy(
            super().__repr__(), self.Relations.__repr__(), "Relations"
        )


@dataclass
class JournalPage(CommonPage):
    Relations: Optional[JournalRelation] = None

    def __repr__(self):
        # ensure every line in rels is indented one more tab for the Relations: block
        if self.Relations:
            return format_relation_heirarchy(
                super().__repr__(), self.Relations.__repr__(), "Relations"
            )
        return super().__repr__()


def indent(text: str, prefix: str = "\t") -> str:
    if not text:
        return ""
    return "\n".join(prefix + line for line in text.splitlines())


def format_relation_heirarchy(
    parent_repr: str, relationString: str, relation_name: str
) -> str:
    if relationString is not None:
        rels_indented = indent(relationString, "\t")
        if parent_repr:
            return parent_repr + f"\n{indent(relation_name)}:\n{rels_indented}"
        else:
            return f"{indent(relation_name)}:\n{rels_indented}"
    return parent_repr


@dataclass
class PaginationResult(Generic[P]):
    results: List[P]
    has_more: bool
    next_cursor: Union[str, None]
