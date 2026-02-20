
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic

from pydantic import UUID4

from common_libs.constants.literal_definitions import (
    JournalRelationsDefinition,
    JunctionRelationDefinition,
    TaskRelationsDefinition,
)
from common_libs.models.client_models import RD, B, J_co, K, P_co

if TYPE_CHECKING:
    from migration_engine.repo.repo_page_interface import RepositoryInterface


@dataclass
class MigrationContext(Generic[K, P_co, J_co, RD]):
    source_datasource_info: DatasourceInfo[K, P_co, RD]
    target_datasource_info: DatasourceInfo[K, P_co, RD]
    journal_datasource_info: DatasourceInfo[K, J_co, RD]
    task_relation_definition: TaskRelationsDefinition
    journal_relation_definition: JournalRelationsDefinition
    junction_relation_definition: JunctionRelationDefinition


@dataclass
class DatasourceInfo(Generic[K, B, RD]):
    datasource_id: UUID4
    repo: RepositoryInterface[K, B, RD]


@dataclass
class ExecutionContext:
    page_size: int
    debug: bool
