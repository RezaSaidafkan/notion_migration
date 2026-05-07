# pylint: disable = C0103
from typing import Generic, List, Optional, Sequence, TypeVar, Union
from uuid import UUID

from pydantic import BaseModel
from sqlmodel import Field

from common_libs.constants.literal_definitions import (
    JunctionRelationDefinition,
    RelationDefinitions,
)

from .api_models import (
    ExternalEmoji,
    IconEmoji,
    IconProperty,
    PeopleProperty,
    RichTextProperty,
    SelectProperty,
    StatusProperty,
    TimelineProperty,
    TitleProperty,
)

# Define K as Page ID type
K = TypeVar("K", bound="PageId")

BP = TypeVar("BP", bound="BasePage")

# Define B as Base type for both P & J
C = TypeVar("C", bound="CommonPage")

# Define P as Page types
P_co = TypeVar("P_co", bound="CommonPage", covariant=True)

# Define J as Page types
J_co = TypeVar("J_co", bound="CommonPage", covariant=True)

# Define R as Relation types
RD = TypeVar("RD", bound=RelationDefinitions)

# Define Related pages
R = TypeVar("R", bound=Union["TaskRelation", "JournalRelation"])


class PageId(BaseModel):
    Id: UUID


class BaseProperties(BaseModel):
    Title: TitleProperty
    Type: Optional[SelectProperty] = None
    Timeline: Optional[TimelineProperty] = None
    Description: Optional[RichTextProperty] = None




# pylint: disable = too-many-instance-attributes
class TaskProperties(BaseProperties):
    Assignee: Optional[PeopleProperty] = None
    Priority: Optional[SelectProperty] = None
    Urgency: Optional[SelectProperty] = None
    Status: Optional[StatusProperty | SelectProperty] = None

    def __repr__(self):
        title = self.Title.__repr__() if self.Title else "<Title: None>"
        typ = self.Type.__repr__() if self.Type else "<Type: None>"
        status = self.Status.__repr__() if self.Status else "<Status: None>"
        timeline = self.Timeline.__repr__() if self.Timeline else "<Date: None>"
        return f"{title} | {typ} | {status} | {timeline}"


class JournalProperties(BaseProperties):
    Status: Optional[
        SelectProperty | StatusProperty
    ] = None  # update in the database, now we have State in source db and Select in journal db

    def __repr__(self):
        title = self.Title.__repr__() if self.Title else "<Title: None>"
        typ = self.Type.__repr__() if self.Type else "<Type: None>"
        status = self.Status.__repr__() if self.Status else "<Status: None>"
        timeline = self.Timeline.__repr__() if self.Timeline else "<Date: None>"
        return f"{title} | {typ} | {status} | {timeline}"


class BaseRelation(Generic[C], BaseModel):
    Ancestors: Optional[Sequence[C]]
    Descendants: Optional[Sequence[C]]

    def __repr__(self):
        rel_parts: List[str] = []
        if self.Descendants:
            for page in self.Descendants:
                page_text = repr(page)
                rel_parts.append(indent(page_text, "\t"))

        if rel_parts:
            return format_relation_heirarchy("", "\n".join(rel_parts), "Descendants")
        return ""


class TaskRelation(BaseRelation["TaskPage"]):
    Journals: Optional[Sequence["JournalPage"]]

    def __repr__(self):
        journ_parts: List[str] = []
        if self.Journals:
            for page in self.Journals:
                page_text = repr(page)
                journ_parts.append(indent(page_text, "\t"))

        base_repr = super().__repr__()
        if journ_parts:
            journ = "\n".join(journ_parts)
            return format_relation_heirarchy(base_repr, journ, "Journals")
        return base_repr


class JournalRelation(BaseRelation["JournalPage"]):
    JunctionRelation: Optional["JunctionRelationDefinition"] = None
    Backtrack: Optional[Sequence["JournalPage"]] = None  # Ancestors
    Forwardtrack: Optional[Sequence["JournalPage"]] = None  # Descendants

    def __repr__(self):
        rel_parts: List[str] = []
        if self.JunctionRelation:
            db_text = repr(self.JunctionRelation)
            rel_parts.append(indent(db_text, "\t"))
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


class BasePage(BaseModel):
    Id: PageId

class CommonPage(BasePage):
    Properties: Union[TaskProperties, JournalProperties] = Field(serialization_alias='properties')
    Icon: Optional[IconProperty | ExternalEmoji | IconEmoji] = Field(serialization_alias='icon')

    def __repr__(self):
        icon = self.Icon.__repr__() if self.Icon else ""
        return f"{icon} {self.Properties}"


class TaskPage(CommonPage):
    Relations: Optional[TaskRelation] = None

    def __repr__(self):
        # ensure every line in rels is indented one more tab for the Relations: block
        return format_relation_heirarchy(
            super().__repr__(), self.Relations.__repr__(), "Relations"
        )


class JournalPage(CommonPage):
    Relations: Optional[JournalRelation] = None

    def __repr__(self):
        # ensure every line in rels is indented one more tab for the Relations: block
        if self.Relations:
            return format_relation_heirarchy(
                super().__repr__(), self.Relations.__repr__(), "Relations"
            )
        return super().__repr__()


class PageUpdate(BaseModel):
    Properties: Union[TaskProperties, JournalProperties] = Field(
        serialization_alias='properties',
        validation_alias='properties')
    Icon: Optional[IconProperty | ExternalEmoji | IconEmoji] = Field(
        serialization_alias='icon',
        validation_alias='icon',
        default=None)
    Cover: Optional[IconProperty | ExternalEmoji | IconEmoji] = Field(
        serialization_alias='cover',
        validation_alias='cover',
        default=None)
    InTrash: Optional[bool] = Field(
        serialization_alias='in_trash',
        validation_alias='in_trash',
        default=None)
    Archived: Optional[bool] = Field(
        serialization_alias='archived',
        validation_alias='archived',
        default=None)
    IsLocked: Optional[bool] = Field(
        serialization_alias='is_locked',
        validation_alias='is_locked',
        default=None)
    Template: Optional[bool] = Field(
        serialization_alias='template',
        validation_alias='template',
        default=None)


def indent(text: str, prefix: str = "\t") -> str:
    if not text:
        return ""
    return "\n".join(prefix + line for line in text.splitlines())


def format_relation_heirarchy(
    parent_repr: str, relationString: Optional[str], relation_name: str
) -> str:
    if relationString:
        rels_indented = indent(relationString, "\t")
        if parent_repr:
            return parent_repr + f"\n{indent(relation_name)}:\n{rels_indented}"
        return f"{indent(relation_name)}:\n{rels_indented}"
    return parent_repr


class PaginationResult(BaseModel, Generic[C]):
    results: List[C]
    has_more: bool
    next_cursor: Union[str, None]


RelativePages = Union["TaskRelation", "JournalRelation"]
