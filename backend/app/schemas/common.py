from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda s: "".join(
            word.capitalize() if i > 0 else word
            for i, word in enumerate(s.split("_"))
        ),
        populate_by_name=True,
        from_attributes=True,
    )


class PaginationParams(CamelModel):
    page: int = 1
    page_size: int = 20


class PaginatedResponse(CamelModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
