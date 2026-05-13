from typing import TypeVar, Generic, Type, cast

from approck_sqlalchemy_utils.mocks import get_session
from approck_sqlalchemy_utils.model import Base
from fastapi import Depends
from multimethod import multimethod as overload
from sqlalchemy.ext.asyncio import AsyncSession

from approck_services.sqlalchemy.base import ORMSQLAlchemyService, SQLAlchemyService

ModelType = TypeVar("ModelType")
FilterType = TypeVar("FilterType")


class FastAPISQLAlchemyService(SQLAlchemyService[ModelType], Generic[ModelType]):
    def __init__(self, session: AsyncSession = Depends(get_session)) -> None:
        super().__init__(session)


class FastAPIORMSQLAlchemyService(ORMSQLAlchemyService[ModelType, FilterType], Generic[ModelType, FilterType]):
    def __init__(self, session: AsyncSession = Depends(get_session)) -> None:
        super().__init__(session)


@overload
def make_service_type(model_cls: Type[ModelType]) -> Type[FastAPISQLAlchemyService[ModelType]]:
    class_name = "{0.__name__}{1.__name__}".format(model_cls, FastAPISQLAlchemyService)
    class_bases = (FastAPISQLAlchemyService,)
    class_namespace = {
        "model_cls": model_cls,
    }
    return cast(Type[FastAPISQLAlchemyService[ModelType]], type(class_name, class_bases, class_namespace))


@overload
def make_service_type(
    model_cls: Type[ModelType], filter_cls: Type[FilterType]
) -> Type[FastAPIORMSQLAlchemyService[ModelType, FilterType]]:
    class_name = "{0.__name__}{1.__name__}".format(model_cls, FastAPIORMSQLAlchemyService)
    class_bases = (FastAPIORMSQLAlchemyService,)
    class_namespace = {
        "model_cls": model_cls,
        "filter_cls": filter_cls,
    }

    return cast(
        Type[FastAPIORMSQLAlchemyService[ModelType, FilterType]], type(class_name, class_bases, class_namespace)
    )


BaseFastAPISQLAlchemyService = make_service_type(Base)
