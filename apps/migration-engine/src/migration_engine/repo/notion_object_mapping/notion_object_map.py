from typing import Any, Dict, overload

from common_libs.constants.literal_definitions import (
    JournalRelationsDefinition,
    JunctionRelationDefinition,
    TaskRelationsDefinition,
)
from common_libs.models.client_models import BasePage

type Relation = JunctionRelationDefinition | JournalRelationsDefinition | TaskRelationsDefinition

@overload
def translate(relation: JunctionRelationDefinition, page: BasePage) -> Dict[str, Any]: ...


@overload
def translate(relation: JournalRelationsDefinition, page: BasePage) -> Dict[str, Any]: ...


@overload
def translate(relation: TaskRelationsDefinition, page: BasePage) -> Dict[str, Any]: ...


def translate(relation: Relation, page: BasePage) -> Dict[str, Any]:
    return {
            "property": str(relation.value),
            "relation": {"contains": str(page.Id.Id)},
            }
