from typing import Any, Callable, ClassVar, Dict, Optional, Protocol, Type

from pydantic import BaseModel


class DataclassProtocol(Protocol):
    '''Typehint for dataclasses'''
    __dataclass_fields__: ClassVar[Dict[str, Any]]
    __dataclass_params__: ClassVar[Any]
    __post_init__: ClassVar[Optional[Callable]]


class PydanticDataclassProtocol(DataclassProtocol):
    '''Typehint for pydantic dataclasses'''
    __pydantic_run_validation__: ClassVar[bool]
    __post_init_post_parse__: ClassVar[Callable[..., None]]
    __pydantic_initialised__: ClassVar[bool]
    __pydantic_model__: ClassVar[Type[BaseModel]]
    __pydantic_validate_values__: ClassVar[Callable[['PydanticDataclassProtocol'], None]]
    __pydantic_has_field_info_default__: ClassVar[bool]  # whether a `pydantic.Field` is used as default value
