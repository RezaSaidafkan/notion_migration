from dataclasses import dataclass
from typing import Any, List, Optional, Dict
from dataclasses_json import DataClassJsonMixin
from dateutil import parser


@dataclass
class IconProperty(DataClassJsonMixin):
    type: str
    emoji: str

    def __repr__(self):
        return self.emoji


@dataclass
class Relation(DataClassJsonMixin):
    id: str


@dataclass
class RelationProperty(DataClassJsonMixin):
    has_more: bool
    id: str
    relation: List[Relation]
    type: str

    def __repr__(self):
        return ", ".join([rel.__repr__() for rel in self.relation])


@dataclass
class Person(DataClassJsonMixin):
    type: str
    id: str
    name: str
    avatar_url: Optional[str] = None
    object: Optional[str] = None
    person: Optional[Dict[str, Any]] = None

    def __repr__(self):
        return self.name


@dataclass
class PeopleProperty(DataClassJsonMixin):
    id: str
    people: List[Person]
    type: str

    def __repr__(self):
        return ", ".join([person.__repr__() for person in self.people])


@dataclass
class SelectOption(DataClassJsonMixin):
    color: str
    id: str
    name: str

    def __repr__(self):
        return self.name


@dataclass
class SelectProperty(DataClassJsonMixin):
    id: str
    select: SelectOption
    type: str

    def __repr__(self):
        return self.select.__repr__()


@dataclass
class StatusOption(DataClassJsonMixin):
    id: str
    name: str
    color: str

    def __repr__(self):
        return self.name


@dataclass
class StatusProperty(DataClassJsonMixin):
    id: str
    status: StatusOption
    type: str

    def __repr__(self):
        return self.status.__repr__()


@dataclass
class RichTextText(DataClassJsonMixin):
    content: str
    link: Optional[Any] = None


@dataclass
class Annotations(DataClassJsonMixin):
    bold: bool
    code: bool
    color: str
    italic: bool
    strikethrough: bool
    underline: bool


@dataclass
class RichTextItem(DataClassJsonMixin):
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


@dataclass
class RichTextProperty(DataClassJsonMixin):
    id: str
    type: str
    rich_text: List[RichTextItem]

    def __repr__(self):
        return " ".join([item.plain_text for item in self.rich_text])


@dataclass
class DateProperty(DataClassJsonMixin):
    @dataclass
    class DateValue(DataClassJsonMixin):
        start: Optional[str]
        end: Optional[str]
        time_zone: Optional[str]

    id: str
    type: str
    date: DateValue

    def _fmt_iso(self, iso: Optional[str]) -> str:
        if not iso:
            return ""
        dt = parser.isoparse(iso)
        return dt.strftime("%Y-%m-%d %H:%M")

    def __repr__(self) -> str:
        if not self.date:
            return "<Date: None>"
        start = self._fmt_iso(self.date.start)
        end = self._fmt_iso(self.date.end)
        tz = self.date.time_zone
        if end:
            return f"{start} → {end}" + (f" ({tz})" if tz else "")
        return f"{start}" + (f" ({tz})" if tz else "")


@dataclass
class TitleText(DataClassJsonMixin):
    content: str
    link: Optional[Any]

    def __repr__(self):
        return self.content


@dataclass
class TitleItem(DataClassJsonMixin):
    type: str
    annotations: Optional[Annotations] = None
    href: Optional[str] = None
    plain_text: Optional[str] = None
    text: Optional[TitleText] = None

    def __repr__(self):
        return self.text.__repr__() if self.text else ""


@dataclass
class TitleProperty(DataClassJsonMixin):
    id: str
    title: List[TitleItem]
    type: str

    def __repr__(self):
        return " ".join([item.__repr__() for item in self.title])


@dataclass
class MultiSelectOption(DataClassJsonMixin):
    color: Optional[str]
    id: Optional[str]
    name: Optional[str]


@dataclass
class MultiSelectProperty(DataClassJsonMixin):
    id: str
    multi_select: List[MultiSelectOption]
    type: str


@dataclass
class CheckboxProperty(DataClassJsonMixin):
    checkbox: bool
    id: str
    type: str


@dataclass
class UrlProperty(DataClassJsonMixin):
    id: str
    type: str
    url: Optional[str]


@dataclass
class ApiPageProperties(DataClassJsonMixin):
    # Required per user's request
    Title: TitleProperty
    Type: SelectProperty
    Status: StatusProperty | SelectProperty
    Timeline: DateProperty

    # Other fields (optional)
    Assignee: Optional[PeopleProperty] = None
    Priority: Optional[SelectProperty] = None
    Urgency: Optional[SelectProperty] = None
    Description: Optional[RichTextProperty] = None
    Ancestors: Optional[RelationProperty] = None
    Descendants: Optional[RelationProperty] = None
    Journals: Optional[RelationProperty] = None


@dataclass
class ApiPage(DataClassJsonMixin):
    id: str
    icon: Optional[IconProperty]
    properties: ApiPageProperties
