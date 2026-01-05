from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel

External = Literal["external"]
Emoji = Literal["emoji"]


class ExternalEmoji(BaseModel):
    type: External
    external: dict


class IconProperty(BaseModel):
    type: Emoji
    emoji: Optional[str]

    def __repr__(self):
        return self.emoji


class Relation(BaseModel):
    id: str


class RelationProperty(BaseModel):
    has_more: bool
    id: str
    relation: List[Relation]
    type: str

    def __repr__(self):
        return ", ".join([rel.__repr__() for rel in self.relation])


class Person(BaseModel):
    type: str
    id: str
    name: str
    avatar_url: Optional[str] = None
    object: Optional[str] = None
    person: Optional[Dict[str, Any]] = None

    def __repr__(self):
        return self.name


class PeopleProperty(BaseModel):
    id: str
    people: List[Person]
    type: str

    def __repr__(self):
        return ", ".join([person.__repr__() for person in self.people])


class SelectOption(BaseModel):
    color: str
    id: str
    name: str

    def __repr__(self):
        return self.name


class SelectProperty(BaseModel):
    id: str
    type: str
    select: Optional[SelectOption] = None

    def __repr__(self):
        if self.select:
            return self.select.__repr__()


class StatusOption(BaseModel):
    id: str
    name: str
    color: str

    def __repr__(self):
        return self.name


class StatusProperty(BaseModel):
    id: str
    status: StatusOption
    type: str

    def __repr__(self):
        return self.status.__repr__()


class RichTextText(BaseModel):
    content: str
    link: Optional[Any] = None


class Annotations(BaseModel):
    bold: bool
    code: bool
    color: str
    italic: bool
    strikethrough: bool
    underline: bool


class RichTextItem(BaseModel):
    type: str
    annotations: Annotations
    plain_text: str
    text: Optional[RichTextText] = None
    href: Optional[str] = None

    def __repr__(self):
        # text can be None when Notion returns a plain_text-only item or when
        # the JSON payload doesn't include the nested 'text' object. Be defensive.
        if self.text:
            return self.text.content
        if self.plain_text:
            return self.plain_text
        return ""


class RichTextProperty(BaseModel):
    id: str
    type: str
    rich_text: List[RichTextItem]

    def __repr__(self):
        return " ".join([item.plain_text for item in self.rich_text])


class DateProperty(BaseModel):
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    time_zone: Optional[str] = None

    def __repr__(self) -> str:
        if not self.start:
            return "<Date: None>"
        start_str = self.start.strftime("%Y-%m-%d")
        if not self.end:
            return start_str
        end_str = self.end.strftime("%Y-%m-%d")
        return f"{start_str} → {end_str}"


class TimelineProperty(BaseModel):
    id: str
    type: str
    date: Optional[DateProperty] = None

    def __repr__(self):
        return self.date.__repr__() if self.date else "<Date: None>"


class TitleText(BaseModel):
    content: str
    link: Optional[Any]

    def __repr__(self):
        return self.content


class TitleItem(BaseModel):
    type: str
    annotations: Optional[Annotations] = None
    href: Optional[str] = None
    plain_text: Optional[str] = None
    text: Optional[TitleText] = None

    def __repr__(self):
        return self.text.__repr__() if self.text else ""


class TitleProperty(BaseModel):
    id: str
    title: List[TitleItem]
    type: str

    def __repr__(self):
        return " ".join([item.__repr__() for item in self.title])


class MultiSelectOption(BaseModel):
    id: Optional[str]
    name: Optional[str]
    color: Optional[str]


class MultiSelectProperty(BaseModel):
    id: str
    type: str
    multi_select: List[MultiSelectOption]


class CheckboxProperty(BaseModel):
    id: str
    type: str
    checkbox: bool


class UrlProperty(BaseModel):
    id: str
    type: str
    url: Optional[str]


class ApiPageProperties(BaseModel):
    # Required per user's request
    Title: TitleProperty
    Type: SelectProperty
    Status: StatusProperty | SelectProperty  # This was already correct
    Timeline: TimelineProperty

    # Other fields (optional)
    Assignee: Optional[PeopleProperty] = None
    Priority: Optional[SelectProperty] = None
    Urgency: Optional[SelectProperty] = None
    Description: Optional[RichTextProperty] = None
    Ancestors: Optional[RelationProperty] = None
    Descendants: Optional[RelationProperty] = None
    Journals: Optional[RelationProperty] = None


class ApiPage(BaseModel):
    id: str
    icon: Optional[IconProperty | ExternalEmoji]
    properties: ApiPageProperties
