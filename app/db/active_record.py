import functools
from dataclasses import asdict, is_dataclass
from operator import and_
from typing import Any, Callable, ClassVar, Self, Sequence, Type
from uuid import UUID

import sqlalchemy as sa
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.engine import Result, ScalarResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, Session, mapped_column
from sqlalchemy.sql import Select
from sqlalchemy.sql._typing import _ColumnExpressionArgument

from app.api.exceptions import BadRequest, NotFound
from app.schemas.core import PageableResponseDTO
from app.utils.typing import DataclassProtocol, PydanticDataclassProtocol

from .base_class import Base


def update_object(
    obj: Any,
    new_data: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    '''
        Update the object with the new data.
        This does not duplicate the object, but instead is a side-effect operation.

        Returns the old state and the new state dicts. This will only contain updated values.
        Very useful for applying and auditing updates
    '''
    old_state = {}
    new_state = {}

    # Simply loop through all key value pairs, and update them on the ORM instance
    if is_dataclass(new_data):
        new_data = asdict(new_data)

    for k, v in new_data.items():
        if hasattr(obj, k):
            old_attr = getattr(obj, k)
            if old_attr != v:
                old_state[k] = old_attr
                new_state[k] = v
                setattr(obj, k, v)
        else:
            # This should never happen since we validate the request body.
            raise BadRequest(f'{type(obj)} has no attribute: {k}')

    return old_state, new_state


class ActiveRecord(Base):
    '''
        Minimum Active Record ORM Model.

        Our version of the Active Record Pattern
    '''
    __abstract__ = True

    # Override this in your model to specify default query options
    _default_query_options: ClassVar[Callable] = None

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=sa.text("uuid_generate_v4()"))

    # -------------------------------------------------------
    # Common function between sync and asyncio
    # These are helper functions that don't do any IO
    # -------------------------------------------------------
    @classmethod
    def _get_instance_data(
        cls: Type[Self],
        new_data: dict[str, Any] | BaseModel | DataclassProtocol | PydanticDataclassProtocol,
    ) -> dict[str, Any]:
        '''For internal use only. May be overridden.'''
        # Ensure we have a dict to work with.
        if is_dataclass(new_data):
            # This works for both regular dataclasses and pydantic dataclasses
            instance_data = asdict(new_data)
        elif isinstance(new_data, BaseModel):
            instance_data = new_data.dict()
        else:
            instance_data = dict(new_data)

        # Remove fields that aren't part of the model
        for k in list(instance_data.keys()):
            if not hasattr(cls, k):
                del instance_data[k]

        return instance_data

    def _prepare_for_persisting(
        self: Self,
        **kwargs,
    ):
        pass

    def _prepare_for_deletion(
        self: Self,
        session: Session,
        **kwargs,
    ):
        pass

    @classmethod
    def order_query(
        cls: Type[Self],
        sort: str,
        stmt: Select,
    ) -> Select:
        '''
            Parses `sort` string and adds order by clauses to the query.
            Default direction is ascending.
            Expected format:
            * comma delimited columns
            * columns and direction delimited by colon

            Example:
                `given_name:desc,family_name`
            This is equivelent to SQL:
                `ORDER BY "given_name" DESC, "family_name" ASC`
        '''
        sort_columns = filter(None, sort.split(','))  # filter out empty strings
        for sort_column in sort_columns:
            parts = sort_column.split(':')
            # Ignore empty parts
            if not parts:
                continue
            # Validate that sorted column exists.
            elif parts[0] not in cls.get_orm_attrs():
                raise BadRequest("Sort column '{}' is not supported.".format(parts[0]))
            else:
                term = getattr(cls, parts[0])

            if len(parts) == 1:
                stmt = stmt.order_by(sa.asc(term))
            else:
                direction = parts[1].upper()
                if direction == 'ASC':
                    stmt = stmt.order_by(sa.asc(term))
                elif direction == 'DESC':
                    stmt = stmt.order_by(sa.desc(term))
                else:
                    raise BadRequest("Invalid sort direction. '{}'".format(direction))

        return stmt

    @classmethod
    def get_list_query(
        cls: Type[Self],
        # Convenience filter. Makes it easy to get all by a list of ids
        ids: list[str] = None,
        # list or tuple (or even single) filter expression
        additional_filters: _ColumnExpressionArgument[bool] | Sequence[_ColumnExpressionArgument[bool]] = None,
        sort: str = None,
        # Define query options. i.e.: query.options(joinedload('foobar'))
        query_options: list[Any] = None,
    ) -> Select | None:
        '''
            Generates and returns the query to get an all objects that match the filters
        '''
        filter_clauses = []
        if ids:
            filter_clauses.append(cls.id.in_(ids))
        if additional_filters:
            if isinstance(additional_filters, (tuple, list)):
                # Remove 'None' otherwise we can end up with `"foo" = 'a' AND NULL` leading to unexpected results
                safe_filters = [f for f in additional_filters if f is not None]
                if safe_filters:
                    filter_clauses.append(functools.reduce(and_, safe_filters))
            else:
                filter_clauses.append(additional_filters)

        stmt = select(cls)
        if filter_clauses:
            filter_ = functools.reduce(and_, filter_clauses)
            stmt = stmt.filter(filter_)

        query_options = query_options or cls._default_query_options
        if query_options:
            stmt = stmt.options(*query_options)

        if sort:
            stmt = cls.order_query(sort, stmt)

        return stmt

    # -------------------------------------------------------
    # Synchronous functions
    # -------------------------------------------------------
    def save(
        self: Self,
        session: Session,
        commit: bool = True,
    ) -> Self:
        '''
            Saves the object.

            Automatically detects if the object is newly being created or is being updated.
            This does not do event auditing, but does set the object's own audit columns.
        '''
        self._prepare_for_persisting()

        session.add(self)
        if commit:
            session.commit()

        return self

    @classmethod
    def create(
        cls: Type[Self],
        new_data: dict[str, Any] | BaseModel | DataclassProtocol | PydanticDataclassProtocol,
        session: Session,
        commit: bool = True,
    ) -> Self:
        '''
            Saves the object and creates an audit event
        '''
        instance = cls(**cls._get_instance_data(new_data))

        instance.save(commit, session=session)

        return instance

    def update(
        self: Self,
        new_data: dict[str, Any] | BaseModel | DataclassProtocol | PydanticDataclassProtocol,
        session: Session,
        commit: bool = True,
        save_if_no_diff: bool = True,
    ) -> Self:
        '''
            Updates and saves the object, and creates an audit event.

            if no diff, and save_if_no_diff is false, we will not add the object and event to the session
        '''
        new_data = self._get_instance_data(new_data)

        # Only updated values will be part of old_ and new_values
        old_values, new_values = update_object(self, new_data)
        if save_if_no_diff or (old_values != new_values):
            self.save(commit, session=session)

        return self

    def update_with_diff(
        self: Self,
        new_data: dict[str, Any] | BaseModel | DataclassProtocol | PydanticDataclassProtocol,
        session: Session,
        commit: bool = True,
        save_if_no_diff: bool = True,
    ) -> tuple[Self, dict[str, Any], dict[str, Any]]:
        '''
            Updates and saves the object, and creates an audit event. Returns self and the diff objects

            if no diff, and save_if_no_diff is false, we will not add the object and event to the session
        '''
        new_data = self._get_instance_data(new_data)

        old_values, new_values = update_object(self, new_data)
        if save_if_no_diff or (old_values != new_values):
            self.save(commit, session=session)

        return self, old_values, new_values

    def delete(
        self: Self,
        session: Session,
        commit: bool = True,
        **kwargs,
    ) -> None:
        '''
            Deletes the object, and creates an audit event
        '''
        self._prepare_for_deletion(
            session=session,
            **kwargs,
        )

        session.delete(self)
        if commit:
            session.commit()

    @classmethod
    def get(
        cls: Type[Self],
        id: str,
        session: Session,
        raise_if_not_found: bool = False,
        # Define query options. i.e.: query.options(joinedload('foobar'))
        query_options: list[Any] = None,
    ) -> Self:
        '''
            Get's an object by id
        '''
        stmt = select(cls)
        if query_options:
            stmt = stmt.options(*query_options)

        stmt = stmt.filter(cls.id == id)

        entity = session.execute(stmt).scalar_one_or_none()

        if entity is None and raise_if_not_found:
            raise NotFound('{} with id {} not found'.format(cls.__name__, id))

        return entity

    @classmethod
    def get_all(
        cls: Type[Self],
        session: Session,
        offset: int = 0,
        limit: int = 100,
        sort: str = None,
        # Convenience filter. Makes it easy to get all by a list of ids
        ids: list[str] = None,
        # list or tuple (or even single) filter expression
        additional_filters: _ColumnExpressionArgument[bool] | Sequence[_ColumnExpressionArgument[bool]] = None,
        # Define query options. i.e.: query.options(joinedload('foobar'))
        query_options: list[Any] = None,
    ) -> PageableResponseDTO:
        '''
            Get all objects that match the filters with permission checks.
            The response can be returned immediately by an API.
        '''
        stmt = cls.get_list_query(
            ids=ids,
            additional_filters=additional_filters,
            sort=sort,
            query_options=query_options,
        )
        count_stmt = (
            select(sa.func.count())
            .select_from(cls)
        )
        if stmt.whereclause is not None:
            count_stmt = count_stmt.filter(stmt.whereclause)

        resp_items = session.scalars(
            stmt
            .offset(offset)
            .limit(limit),
        ).all()
        total_items = session.scalars(count_stmt).one()

        response = PageableResponseDTO(
            items=resp_items,
            total_items=total_items,
        )
        return response

    # -------------------------------------------------------
    # Asyncio functions
    # -------------------------------------------------------
    async def aio_save(
        self: Self,
        session: AsyncSession,
        commit: bool = True,
    ) -> Self:
        '''
            Saves the object.

            Automatically detects if the object is newly being created or is being updated.
            This does not do event auditing, but does set the object's own audit columns.
        '''
        self._prepare_for_persisting()

        session.add(self)
        if commit:
            await session.commit()
        # Required, otherwise it'll try to load the data outside of the await block
        # when FastAPI automatically loads it.
        await session.refresh(self)

        return self

    @classmethod
    async def aio_create(
        cls: Type[Self],
        new_data: dict[str, Any] | BaseModel | DataclassProtocol | PydanticDataclassProtocol,
        session: AsyncSession,
        commit: bool = True,
    ) -> Self:
        '''
            Saves the object and creates an audit event
        '''
        instance = cls(**cls._get_instance_data(new_data))

        await instance.aio_save(session=session, commit=commit)

        return instance

    async def aio_update(
        self: Self,
        new_data: dict[str, Any] | BaseModel | DataclassProtocol | PydanticDataclassProtocol,
        session: AsyncSession,
        commit: bool = True,
        save_if_no_diff: bool = True,
    ) -> Self:
        '''
            Updates and saves the object, and creates an audit event.

            if no diff, and save_if_no_diff is false, we will not add the object and event to the session
        '''
        new_data = self._get_instance_data(new_data)

        # Only updated values will be part of old_ and new_values
        old_values, new_values = update_object(self, new_data)
        if save_if_no_diff or (old_values != new_values):
            await self.aio_save(session=session, commit=commit)

        return self

    async def aio_update_with_diff(
        self: Self,
        new_data: dict[str, Any] | BaseModel | DataclassProtocol | PydanticDataclassProtocol,
        session: AsyncSession,
        commit: bool = True,
        save_if_no_diff: bool = True,
    ) -> tuple[Self, dict[str, Any], dict[str, Any]]:
        '''
            Updates and saves the object, and creates an audit event. Returns self and the diff objects

            if no diff, and save_if_no_diff is false, we will not add the object and event to the session
        '''
        new_data = self._get_instance_data(new_data)

        old_values, new_values = update_object(self, new_data)
        if save_if_no_diff or (old_values != new_values):
            await self.aio_save(session=session, commit=commit)

        return self, old_values, new_values

    async def aio_delete(
        self: Self,
        session: AsyncSession,
        commit: bool = True,
        **kwargs,
    ) -> None:
        '''
            Deletes the object, and creates an audit event
        '''
        # We don't commit in preparation, so no need to await
        self._prepare_for_deletion(
            session=session,
            **kwargs,
        )

        await session.delete(self)
        if commit:
            await session.commit()

    @classmethod
    async def aio_get(
        cls: Type[Self],
        id: str,
        session: AsyncSession,
        raise_if_not_found: bool = False,
        # Define query options. i.e.: query.options(joinedload('foobar'))
        query_options: list[Any] = None,
    ) -> Self:
        '''
            Get's an object by id with permission checks.
        '''
        stmt = select(cls)
        if query_options:
            stmt = stmt.options(*query_options)

        stmt = stmt.filter(cls.id == id)

        result = await session.execute(stmt)
        entity = result.scalar_one_or_none()

        if entity is None and raise_if_not_found:
            raise NotFound('{} with id {} not found'.format(cls.__name__, id))

        return entity

    @classmethod
    async def aio_get_all(
        cls: Type[Self],
        session: AsyncSession,
        offset: int = 0,
        limit: int = 100,
        sort: str = None,
        # Convenience filter. Makes it easy to get all by a list of ids
        ids: list[str] = None,
        # list or tuple (or even single) filter expression
        additional_filters: _ColumnExpressionArgument[bool] | Sequence[_ColumnExpressionArgument[bool]] = None,
        # Define query options. i.e.: query.options(joinedload('foobar'))
        query_options: list[Any] = None,
    ) -> PageableResponseDTO:
        '''
            Get all objects that match the filters with permission checks.
            The response can be returned immediately by an API.
        '''
        stmt = cls.get_list_query(
            ids=ids,
            additional_filters=additional_filters,
            sort=sort,
            query_options=query_options,
        )
        count_stmt = (
            select(sa.func.count())
            .select_from(cls)
        )
        if stmt.whereclause is not None:
            count_stmt = count_stmt.filter(stmt.whereclause)

        result: ScalarResult = await session.scalars(
            stmt
            .offset(offset)
            .limit(limit),
        )
        resp_items = result.all()

        count_result: ScalarResult = await session.scalars(count_stmt)
        total_items = count_result.one()

        response = PageableResponseDTO(
            items=resp_items,
            total_items=total_items,
        )
        return response
