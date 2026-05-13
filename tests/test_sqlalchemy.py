import dataclasses
from typing import Optional

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from approck_services.sqlalchemy import make_service_type
from tests.models import Author


class AuthorService(make_service_type(Author)):
    async def find_one(self, id_: int) -> Author:
        return await self._find_one(select(Author).where(Author.id == id_))


@dataclasses.dataclass
class AuthorFilter:
    first_name: Optional[str] = None


class AuthorORMService(make_service_type(Author, AuthorFilter)):
    pass


@pytest.mark.asyncio
async def test_sqlalchemy_basic(fx_session: AsyncSession):
    author_service = AuthorService(session=fx_session)
    await author_service.find_one(id_=123)


@pytest.mark.asyncio
async def test_sqlalchemy_orm(fx_session: AsyncSession):
    author_service = AuthorORMService(session=fx_session)
    await author_service.filter(filter_=AuthorFilter(first_name="a"))
