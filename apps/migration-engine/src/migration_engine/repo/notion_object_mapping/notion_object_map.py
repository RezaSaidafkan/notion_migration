from typing import Any, Dict, overload

from common_libs.constants.literal_definitions import (
    JournalRelationsDefinition,
    JunctionRelationDefinition,
    TaskRelationsDefinition,
)
from common_libs.models.client_models import PageId

type Relation = JunctionRelationDefinition | JournalRelationsDefinition | TaskRelationsDefinition

@overload
def translate(relation: JunctionRelationDefinition, page_id: PageId) -> Dict[str, Any]: ...


@overload
def translate(relation: JournalRelationsDefinition, page_id: PageId) -> Dict[str, Any]: ...


@overload
def translate(relation: TaskRelationsDefinition, page_id: PageId) -> Dict[str, Any]: ...


def translate(relation: Relation, page_id: PageId) -> Dict[str, Any]:
    return {
            "property": str(relation.value),
            "relation": {"contains": str(page_id.Id)},
            }
