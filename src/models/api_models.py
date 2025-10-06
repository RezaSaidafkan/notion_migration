
from dataclasses import dataclass
from typing import Any
from dataclasses_json import DataClassJsonMixin

@dataclass
class ApiPageProperties(DataClassJsonMixin):
    Title: Any
    Type: Any
    Assignee: Any
    Priority: Any
    Urgency: Any
    Status: Any
    Timeline: Any
    Description: Any
    Ancestors: Any
    Descendants: Any
    Journals: Any

@dataclass
class ApiPage(DataClassJsonMixin):
    id: str
    icon: Any
    properties: ApiPageProperties

