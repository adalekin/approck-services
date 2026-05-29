from typing import Iterator

import approck_sqlalchemy_utils.session
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from tests.models import Base

approck_sqlalchemy_utils.session.init(url="postgresql+asyncpg://postgres:postgres@localhost:5432/postgres")


@pytest.fixture(autouse=True, scope="session")
def fx_apply_migrations():
    with approck_sqlalchemy_utils.session.current_session() as session:
        Base.metadata.create_all(session.get_bind())
        yield
        session.rollback()


@pytest_asyncio.fixture(name="fx_session", autouse=True, loop_scope="session")
async def fx_session_impl() -> Iterator[AsyncSession]:
    async with approck_sqlalchemy_utils.session.context_session() as session:
        yield session
