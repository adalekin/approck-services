from dataclasses import fields
from typing import Any, Generic, Sequence, Tuple, Type, TypeVar, cast

from approck_sqlalchemy_utils.model import Base
from approck_sqlalchemy_utils.parsers import order_by
from multimethod import multimethod as overload
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import Delete, Select, Update

from approck_services.base import BaseService
from approck_services.sqlalchemy.abstract import AbstractORMSQLAlchemyService, AbstractSQLAlchemyService

ModelType = TypeVar("ModelType")
FilterType = TypeVar("FilterType")


class SQLAlchemyService(AbstractSQLAlchemyService, BaseService, Generic[ModelType]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__()

        self.session = session

    async def _create(self, instance: ModelType) -> ModelType:
        instance = await self._save(instance)
        await self.session.refresh(instance)

        return instance

    async def _find(
        self,
        statement: Select,
        params: Any = None,
        bind_arguments: Any = None,
    ) -> Sequence[ModelType]:
        return (
            (await self.session.scalars(statement=statement, params=params, bind_arguments=bind_arguments))
            .unique()
            .all()
        )

    async def _find_one(
        self,
        statement: Select,
        params: Any = None,
        bind_arguments: Any = None,
    ) -> ModelType | None:
        return await self.session.scalar(statement=statement, params=params, bind_arguments=bind_arguments)

    async def _find_one_or_fail(
        self,
        statement: Select,
        params: Any = None,
        bind_arguments: Any = None,
    ) -> ModelType:
        instance = await self._find_one(statement=statement, params=params, bind_arguments=bind_arguments)

        if instance is None:
            raise NoResultFound(f"{statement.froms} not found")

        return instance

    async def _update(
        self,
        statement: Update,
        params: Any = None,
        bind_arguments: Any = None,
    ) -> None:
        await self.session.execute(statement=statement, params=params, bind_arguments=bind_arguments)
        await self.session.commit()

    async def _delete(
        self,
        statement: Delete,
        params: Any = None,
        bind_arguments: Any = None,
    ) -> None:
        await self.session.execute(
            statement=statement,
            params=params,
            bind_arguments=bind_arguments,
        )
        await self.session.commit()

    @overload
    async def _remove(self, instance: ModelType) -> None:
        await self.session.delete(instance)
        await self.session.commit()

    @overload
    async def _remove(self, instances: Sequence[ModelType]) -> None:
        for instance in instances:
            await self.session.delete(instance)

        await self.session.commit()

    @overload
    async def _pre_save(self, instance: ModelType, **kwargs) -> ModelType:
        return await self.session.merge(instance, **kwargs)

    @overload
    async def _pre_save(self, instances: Sequence[ModelType]) -> Sequence[ModelType]:
        self.session.add_all(instances)
        await self.session.flush(instances)
        return instances

    @overload
    async def _save(self, instance: ModelType, **kwargs) -> ModelType:
        instance = await self._pre_save(instance, **kwargs)
        await self.session.commit()
        return instance

    @overload
    async def _save(self, instances: Sequence[ModelType]) -> Sequence[ModelType]:
        instances = await self._pre_save(instances)
        await self.session.commit()
        return instances


class ORMSQLAlchemyService(AbstractORMSQLAlchemyService, SQLAlchemyService[ModelType], Generic[ModelType, FilterType]):
    RESERVED_FIELDS = ("order_by",)

    async def create(self, dto: BaseModel) -> ModelType:
        instance = await self._create(self.model_cls(**dto.model_dump()))
        await self.session.refresh(instance)

        return instance

    async def filter_statement(self, filter_: FilterType) -> Tuple[AsyncSession, Select]:
        where = []

        for field in fields(self.filter_cls):
            filter_field = getattr(filter_, field.name)

            if filter_field is None:
                continue

            if field.name not in self.RESERVED_FIELDS:
                if "__" in field.name:
                    field_name, field_op = field.name.split("__", 1)
                    model_field = getattr(self.model_cls, field_name)

                    if field_op == "lt":
                        where.append(model_field < filter_field)
                    elif field_op == "gt":
                        where.append(model_field > filter_field)
                    elif field_op == "in":
                        where.append(model_field.in_(filter_field))
                    elif field_op == "isnull":
                        if filter_field:
                            where.append(model_field.is_(None))
                        else:
                            where.append(model_field.isnot(None))
                else:
                    model_field = getattr(self.model_cls, field.name)

                    where.append(model_field == filter_field)

        statement = select(self.model_cls).where(*where)

        if hasattr(filter_, "order_by") and filter_.order_by:
            statement = statement.order_by(*order_by.parse(filter_.order_by))

        return self.session, statement

    async def filter(self, filter_: FilterType) -> Sequence[ModelType]:
        session, statement = await self.filter_statement(filter_)

        return (await session.scalars(statement=statement)).unique().all()

    async def find_one(self, id_: int) -> ModelType | None:
        return await self._find_one(select(self.model_cls).where(self.model_cls.id == id_))

    async def find_one_or_fail(self, id_: int) -> ModelType:
        return await self._find_one_or_fail(select(self.model_cls).where(self.model_cls.id == id_))

    async def update_indirect(self, instance: ModelType, dto: BaseModel) -> ModelType:
        for k, v in dto.model_dump(exclude_unset=True).items():
            setattr(instance, k, v)

        instance = await self._save(instance)
        await self.session.refresh(instance)

        return instance

    async def update(self, id_: int, dto: BaseModel) -> ModelType:
        instance = await self.find_one_or_fail(id_)
        return await self.update_indirect(instance=instance, dto=dto)

    async def delete(self, id_: int) -> None:
        instance = await self.find_one_or_fail(id_)
        await self._remove(instance)


@overload
def make_service_type(model_cls: Type[ModelType]) -> Type[SQLAlchemyService[ModelType]]:
    class_name = "{0.__name__}{1.__name__}".format(model_cls, SQLAlchemyService)
    class_bases = (SQLAlchemyService,)
    class_namespace = {
        "model_cls": model_cls,
    }
    return cast(Type[SQLAlchemyService[ModelType]], type(class_name, class_bases, class_namespace))


@overload
def make_service_type(
    model_cls: Type[ModelType], filter_cls: Type[FilterType]
) -> Type[ORMSQLAlchemyService[ModelType, FilterType]]:
    class_name = "{0.__name__}{1.__name__}".format(model_cls, ORMSQLAlchemyService)
    class_bases = (ORMSQLAlchemyService,)
    class_namespace = {
        "model_cls": model_cls,
        "filter_cls": filter_cls,
    }

    return cast(Type[ORMSQLAlchemyService[ModelType, FilterType]], type(class_name, class_bases, class_namespace))


BaseSQLAlchemyService = make_service_type(Base)
