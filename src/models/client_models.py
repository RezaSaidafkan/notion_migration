
from dataclasses import dataclass
from typing import Any
from dataclasses_json import DataClassJsonMixin

@dataclass
class ClientPageProperties(DataClassJsonMixin):
    Title: Any
    Type: Any
    Assignee: Any
    Priority: Any
    Urgency: Any
    Status: Any
    Timeline: Any
    Description: Any

@dataclass
class ClientPageRelations(DataClassJsonMixin):
    Journal: Any
    Ancestor: Any
    Descendants: Any
    
@dataclass
class ClientPage(DataClassJsonMixin):
    id: str
    icon: Any
    properties: ClientPageProperties
    relations: ClientPageRelations
