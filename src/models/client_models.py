
from dataclasses import dataclass
from typing import Any, Optional
from dataclasses_json import DataClassJsonMixin
from models.api_models import DateProperty, PeopleProperty, RelationProperty, RichTextProperty, SelectProperty, StatusProperty, Icon, TitleProperty

@dataclass
class ClientPageProperties(DataClassJsonMixin):
    Type: TitleProperty
    Title: TitleProperty
    Assignee: PeopleProperty
    Priority: SelectProperty
    Urgency: SelectProperty
    Status: StatusProperty
    Timeline: DateProperty
    Description: RichTextProperty
    Ancestors: RelationProperty
    Descendants: RelationProperty
    Journals: RelationProperty

@dataclass
class ClientPageRelations(DataClassJsonMixin):
    Journals: RelationProperty
    Ancestors: RelationProperty
    Descendants: RelationProperty
    
@dataclass
class ClientPage(DataClassJsonMixin):
    id: str
    icon: Optional[Icon]
    properties: ClientPageProperties
    relations: ClientPageRelations
