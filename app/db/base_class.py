from typing import Generator

import sqlalchemy as sa
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import DeclarativeBase, declared_attr

from app.utils import to_snake_case


class Base(DeclarativeBase):
    # Generate __tablename__ automatically

    @declared_attr.directive
    def __tablename__(cls) -> str:
        # Source: https://stackoverflow.com/a/46493824/3776765
        return to_snake_case(cls.__name__)

    @classmethod
    def get_orm_attrs(cls: DeclarativeBase) -> Generator[str, None, None]:
        '''Get'''
        return (
            x.__name__ if type(x) == hybrid_property else x.key
            for x in sa.inspect(cls).all_orm_descriptors
        )
