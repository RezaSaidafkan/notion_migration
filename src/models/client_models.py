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

# Define T
T = TypeVar("T", bound=Union["Page", "JournalPage"])
# T = TypeVar("T", Page, JournalPage)


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
class BaseHierarchyProperty(Generic[T], DataClassJsonMixin):
    Ancestors: Optional[List["T"]]
    Descendants: Optional[List["T"]]

    def __repr__(self):
        rel_parts = []
        if self.Descendants:
            for page in self.Descendants:
                page_text = repr(page)
                rel_parts.append(indent(page_text, "\t"))

        return format_relation_heirarchy(
            super().__repr__(), "\n".join(rel_parts), "Base.Descendants"
        )


@dataclass
class PageRelation(Generic[T], BaseHierarchyProperty[T]):
    Journals: Optional[List["T"]]

    def __repr__(self):
        journ_parts = []
        if self.Journals:
            for page in self.Journals:
                page_text = repr(page)
                journ_parts.append(indent(page_text, "\t"))

            journ = "\n".join(journ_parts)
        return format_relation_heirarchy(super().__repr__(), journ, "Page.Journals")


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

        rels = "\n".join(rel_parts)
        return format_relation_heirarchy(super().__repr__(), rels, "Journal.Database")


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
            super().__repr__(), self.Relations.__repr__(), "Page.Relations"
        )


@dataclass
class JournalPage(CommonPage):
    Relations: Optional[JournalRelation] = None

    def __repr__(self):
        # ensure every line in rels is indented one more tab for the Relations: block
        return format_relation_heirarchy(
            super().__repr__(), self.Relations.__repr__(), "Journal.Relations"
        )


def indent(text: str, prefix: str = "\t") -> str:
    if not text:
        return ""
    return "\n".join(prefix + line for line in text.splitlines())


def format_relation_heirarchy(
    parent_repr: str, relationString: str, relation_name
) -> str:
    if relationString is not None:
        rels_indented = indent(relationString, "\t")
        # print(relation_name, parent_repr , len(rels_indented))
        return parent_repr + f"\n\t{relation_name}:\n{rels_indented}"
    return parent_repr


@dataclass
class PaginationResult(Generic[T]):
    results: List[T]
    has_more: bool
    next_cursor: Union[str, None]
