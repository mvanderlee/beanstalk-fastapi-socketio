from typing import Generic, TypeVar

from pydantic import Field
from pydantic.generics import GenericModel

T = TypeVar("T")


# FYI: can't use dataclass and generics in Pydantic
class PageableResponseDTO(GenericModel, Generic[T]):
    items: list[T] = Field(default_factory=list)
    num_items: int = 0
    total_items: int = 0

    def __init__(self, **data):
        data["num_items"] = len(data['items'])
        super().__init__(**data)
