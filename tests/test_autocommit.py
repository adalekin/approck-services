"""Transaction-boundary behaviour of the ``autocommit`` flag.

``autocommit=True`` (default) keeps the 1.0.x behaviour: write methods commit their
own transaction, so a write is visible from an independent session immediately.
``autocommit=False`` makes the service commit-free: writes flush instead, so the row
is visible to later reads in the *same* session but stays invisible to other sessions
until the caller commits.
"""

import dataclasses
import uuid
from typing import AsyncIterator, Optional

import approck_sqlalchemy_utils.session
import pytest
import pytest_asyncio
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from approck_services.sqlalchemy import make_service_type
from tests.models import Author


@dataclasses.dataclass
class AuthorFilter:
    email: Optional[str] = None


class AuthorService(make_service_type(Author, AuthorFilter)):
    pass


class AuthorNoCommitService(make_service_type(Author, AuthorFilter)):
    autocommit = False


class AuthorCreate(BaseModel):
    first_name: str
    email: str


def _unique_email() -> str:
    return f"{uuid.uuid4().hex}@example.com"


@pytest_asyncio.fixture(loop_scope="session")
async def fx_other_session() -> AsyncIterator[AsyncSession]:
    """A second, independent session used to observe cross-transaction visibility."""
    async with approck_sqlalchemy_utils.session.context_session() as session:
        yield session


async def _purge(email: str) -> None:
    async with approck_sqlalchemy_utils.session.context_session() as session:
        await session.execute(delete(Author).where(Author.email == email))
        await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_autocommit_true_commits(fx_session: AsyncSession, fx_other_session: AsyncSession):
    email = _unique_email()
    service = AuthorService(session=fx_session)
    try:
        author = await service.create(AuthorCreate(first_name="Ada", email=email))

        # Committed: an independent session sees the row without any commit from the caller.
        found = await fx_other_session.scalar(select(Author).where(Author.id == author.id))
        assert found is not None
    finally:
        await _purge(email)


@pytest.mark.asyncio(loop_scope="session")
async def test_autocommit_false_flushes_without_commit(fx_session: AsyncSession, fx_other_session: AsyncSession):
    email = _unique_email()
    service = AuthorNoCommitService(session=fx_session)

    author = await service.create(AuthorCreate(first_name="Grace", email=email))

    # Flushed: visible to a later read in the same session (id assigned, row queryable).
    same = await fx_session.scalar(select(Author).where(Author.id == author.id))
    assert same is not None

    # Not committed: an independent session must not see it yet.
    other = await fx_other_session.scalar(select(Author).where(Author.id == author.id))
    assert other is None

    # The caller owns the boundary — nothing reaches the database until this commit.
    await fx_session.commit()
    try:
        now_visible = await fx_other_session.scalar(select(Author).where(Author.id == author.id))
        assert now_visible is not None
    finally:
        await _purge(email)


@pytest.mark.asyncio(loop_scope="session")
async def test_autocommit_false_remove_flushes_without_commit(fx_session: AsyncSession, fx_other_session: AsyncSession):
    email = _unique_email()

    # Seed a committed row via the default (autocommit) service.
    seed = AuthorService(session=fx_session)
    author = await seed.create(AuthorCreate(first_name="Edsger", email=email))
    author_id = author.id

    try:
        no_commit = AuthorNoCommitService(session=fx_session)
        await no_commit.delete(author_id)

        # Deletion flushed: gone within the same session.
        same = await fx_session.scalar(select(Author).where(Author.id == author_id))
        assert same is None

        # But not committed: still present for an independent session.
        other = await fx_other_session.scalar(select(Author).where(Author.id == author_id))
        assert other is not None

        # Rolling back the uncommitted deletion brings the row back.
        await fx_session.rollback()
        restored = await fx_session.scalar(select(Author).where(Author.id == author_id))
        assert restored is not None
    finally:
        await _purge(email)


@pytest.mark.asyncio(loop_scope="session")
async def test_autocommit_false_update_flushes_without_commit(fx_session: AsyncSession, fx_other_session: AsyncSession):
    email = _unique_email()

    seed = AuthorService(session=fx_session)
    author = await seed.create(AuthorCreate(first_name="Alan", email=email))
    author_id = author.id

    try:
        no_commit = AuthorNoCommitService(session=fx_session)
        await no_commit.update_indirect(author, AuthorCreate(first_name="Turing", email=email))

        # Flushed in-session.
        same = await fx_session.scalar(select(Author).where(Author.id == author_id))
        assert same.first_name == "Turing"

        # Not visible to another session until commit.
        other = await fx_other_session.scalar(select(Author).where(Author.id == author_id))
        assert other.first_name == "Alan"

        await fx_session.commit()
    finally:
        await _purge(email)
