# from typing import Sequence

# from sqlmodel import Field, SQLModel

# from common_libs.models.client_models import PageId
# from common_libs.models.tracing_models import Monad


# class RelationSet(SQLModel):
#     id: PageId = Field(primary_key=True)
#     target_page_id: PageId
#     outcome: Monad


# class Loaded(SQLModel):
#     id: PageId = Field(primary_key=True)
#     outcome: Monad
#     target_page_id: PageId


# class Extracted(SQLModel):
#     id: PageId = Field(primary_key=True)
#     outcome: Monad


# class ExtractedSubpages(SQLModel):
#     id: PageId = Field(primary_key=True)
#     outcome: Monad
#     sub_pages: Sequence[PageId]


# class RelationsSet(SQLModel):
#     id: PageId = Field(primary_key=True)
#     outcome: Monad
#     relations_set: Sequence[RelationSet]

# type EtlBody = Extracted | ExtractedSubpages | Loaded | RelationsSet
