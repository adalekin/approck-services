from abc import ABC
from typing import Generic, Type, TypeVar

ModelType = TypeVar("ModelType")
FilterType = TypeVar("FilterType")


class AbstractSQLAlchemyService(ABC, Generic[ModelType]):
    """Base contract for a service bound to a single ORM model."""

    model_cls: Type[ModelType]


class AbstractORMSQLAlchemyService(AbstractSQLAlchemyService[ModelType], Generic[ModelType, FilterType]):
    """ORM service that also binds a filter dataclass type."""

    filter_cls: Type[FilterType]
