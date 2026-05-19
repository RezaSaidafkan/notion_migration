# pylint: disable = C0103
from typing import Dict, Generic, List, Optional, Sequence, TypeVar, Union
from uuid import UUID

from pydantic import BaseModel, model_serializer
from sqlmodel import Field

from common_libs.constants.literal_definitions import RelationDefinitions

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
RelativePages = Union["Ancestors", "Descendants", "ForwardTrack", "BackTrack", "JunctionRelation"]


class PageId(BaseModel):
    Id: UUID


class Relation(BaseModel):
    Items: Sequence[TaskPage | JournalPage]

    @model_serializer(mode="plain")
    def serialize_items(self) -> Dict[str, List[str] | str]:
        return {"relation": [str(item.Id.Id) for item in self.Items],
                "type": "relation"}


class Ancestors(Relation):
    pass

class Descendants(Relation):
    pass

class Journals(Relation):
    pass

class ForwardTrack(Relation):
    pass

class BackTrack(Relation):
    pass

class JunctionRelation(Relation):
    pass

class BaseProperties(BaseModel):
    Title: TitleProperty
    Type: Optional[SelectProperty] = None
    Timeline: Optional[TimelineProperty] = None
    Description: Optional[RichTextProperty] = None
    # Relations
    Ancestors: Optional[Ancestors] = None
    Descendants: Optional[Descendants] = None


# pylint: disable = too-many-instance-attributes
class TaskProperties(BaseProperties):
    Assignee: Optional[PeopleProperty] = None
    Priority: Optional[SelectProperty] = None
    Urgency: Optional[SelectProperty] = None
    Status: Optional[StatusProperty | SelectProperty] = None
    # Relations
    Journals: Optional[Journals] = None


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

    # Relations
    Forwardtrack: Optional[ForwardTrack] = None
    Backtrack: Optional[BackTrack] = None
    JunctionRelation: Optional[JunctionRelation] = None

    def __repr__(self):
        title = self.Title.__repr__() if self.Title else "<Title: None>"
        typ = self.Type.__repr__() if self.Type else "<Type: None>"
        status = self.Status.__repr__() if self.Status else "<Status: None>"
        timeline = self.Timeline.__repr__() if self.Timeline else "<Date: None>"
        return f"{title} | {typ} | {status} | {timeline}"


class BasePage(BaseModel):
    Id: PageId

class CommonPage(BasePage):
    Icon: Optional[IconProperty | ExternalEmoji | IconEmoji] = Field(serialization_alias='icon')

    def __repr__(self):
        icon = self.Icon.__repr__() if self.Icon else ""
        return f"{icon}"


class TaskPage(CommonPage):
    Properties: TaskProperties = Field(serialization_alias='properties')

    def __repr__(self):
        # ensure every line in rels is indented one more tab for the Relations: block
        # ensure every line in rels is indented one more tab for the Relations: block
        # if self.Properties.Relations:
        #     return format_relation_heirarchy(
        #         super().__repr__(), self.Relations.__repr__(), "Relations"
        #     )
        return super().__repr__() + self.Properties.__repr__()


class JournalPage(CommonPage):
    Properties: JournalProperties = Field(serialization_alias='properties')

    def __repr__(self):
        # ensure every line in rels is indented one more tab for the Relations: block
        # if self.Properties.Relations:
        #     return format_relation_heirarchy(
        #         super().__repr__(), self.Relations.__repr__(), "Relations"
        #     )
        return super().__repr__() + self.Properties.__repr__()


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
