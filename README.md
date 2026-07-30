# approck-services

[![CI](https://github.com/adalekin/approck-services/actions/workflows/ci.yml/badge.svg)](https://github.com/adalekin/approck-services/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/approck-services.svg)](https://pypi.org/project/approck-services/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Small Python helpers for **async SQLAlchemy** and **FastAPI** service layers, plus an optional **S3-compatible upload** helper. The SQLAlchemy pieces build on [`approck-sqlalchemy-utils`](https://pypi.org/project/approck-sqlalchemy-utils/) (sessions, base models, ordering helpers).

## Features

- **SQLAlchemy (async)**: generic `SQLAlchemyService` and `ORMSQLAlchemyService` with CRUD-style helpers, filter dataclasses (`__lt`, `__gt`, `__in`, `__isnull`), and `make_service_type()` to bind a concrete model (and optional filter) to a service class.
- **FastAPI**: thin wrappers that inject `AsyncSession` via `Depends`, plus `make_service_type()` variants for route dependencies.
- **Upload (optional)**: `BaseUploadService` for uploading bytes, file-like objects, or remote URLs to S3-compatible storage using `aioboto3`.

## Requirements

- Python 3.10+
- Core dependency: [`multimethod`](https://pypi.org/project/multimethod/) (used for `@overload`-style dispatch).

Optional extras pull in FastAPI, SQLAlchemy utilities, or AWS SDK as needed.

## Installation

```bash
pip install approck-services
```

Install optional components:

```bash
pip install "approck-services[fastapi]"
pip install "approck-services[sqlalchemy]"
pip install "approck-services[upload]"
```

With [uv](https://docs.astral.sh/uv/) in your own project (pick extras you need):

```bash
uv add 'approck-services[sqlalchemy,fastapi,upload]'
```

## Usage

Install the pieces you need. Imports below assume **`approck-services[sqlalchemy]`**; FastAPI examples also need **`[fastapi]`**. Session wiring uses **`get_session`** from **`approck-sqlalchemy-utils`** (configure the real session in your app; tests often use **`approck_sqlalchemy_utils.mocks.get_session`**).

### `make_service_type(model_cls)`

Returns a small async **SQLAlchemy** service bound to **`model_cls`**. It exposes **protected** helpers such as **`_find_one`**, **`_find`**, **`_create`**, **`_save`**, **`_remove`**, **`_update`**, **`_delete`** — you are expected to **subclass** and add public methods that build **`select()` / `update()` / `delete()`** statements for your domain.

```python
from sqlalchemy import select

from approck_services.sqlalchemy import make_service_type
from myapp.models import User


class UserService(make_service_type(User)):
    async def get_by_email(self, email: str) -> User | None:
        return await self._find_one(select(User).where(User.email == email))
```

For **FastAPI**, import **`make_service_type`** from **`approck_services.fastapi`** instead. The generated class takes **`session: AsyncSession = Depends(get_session)`** and can be used as a route dependency.

```python
from approck_services.fastapi import make_service_type
from myapp.models import User

UserService = make_service_type(User)
```

### `make_service_type(model_cls, filter_cls)`

Returns an **ORM-shaped** service (**`ORMSQLAlchemyService`**) with a **`filter_cls`** dataclass. Public methods include **`filter`**, **`filter_statement`**, **`create`**, **`update`**, **`update_indirect`**, **`delete`**, **`find_one`**, **`find_one_or_fail`**. These assume the model has a numeric primary key **`id`** (used in **`find_one` / `update` / `delete`**).

- **`create` / `update` / `update_indirect`** accept a **Pydantic** **`BaseModel`**; fields are mapped with **`model_dump()`** (and **`exclude_unset=True`** on update) onto the ORM instance.
- **`filter` / `filter_statement`**: for each **non-`None`** field on the filter dataclass, a **`WHERE`** clause is added. Plain fields mean **equality** on the same-named column on **`model_cls`**. Suffixes after **`__`** (one double underscore) are interpreted as operators on the prefix name: **`lt`**, **`gt`**, **`in`**, **`isnull`** (e.g. **`created_at__lt`**, **`id__in`**, **`deleted_at__isnull`**).
- Field **`order_by`** is reserved: if present and truthy, it is passed to **`approck-sqlalchemy-utils`** **`order_by.parse`**.

```python
import dataclasses
from typing import Optional

from approck_services.sqlalchemy import make_service_type
from myapp.models import User


@dataclasses.dataclass
class UserFilter:
    email: Optional[str] = None
    age__gt: Optional[int] = None
    order_by: Optional[str] = None


UserService = make_service_type(User, UserFilter)
```

The FastAPI variant is the same factory from **`approck_services.fastapi`**; **`filter_statement`** / **`create`** / etc. can be overridden in a subclass when you need **`selectinload`**, multi-table writes, or extra **`Depends`**. Call **`super().__init__(session)`** and keep **`session=Depends(get_session)`** aligned with the generated base.

### Transaction boundary (`autocommit`)

By default (**`autocommit = True`**) every write helper (**`create`**, **`update`**, **`update_indirect`**, **`delete`**, and the low-level **`_save` / `_update` / `_delete` / `_remove`**) commits its own transaction. This is the historical behaviour and stays the default, so existing code is unaffected.

Set **`autocommit = False`** on a service subclass to make it **commit-free**: writes **flush** instead of committing, and the **caller owns the transaction boundary**. Flushing keeps written rows visible to later reads in the same session, so composing several services into one atomic operation no longer needs a `commit` flag threaded through the call chain.

```python
class UserService(make_service_type(User, UserFilter)):
    autocommit = False


# The caller opens the boundary; both writes commit together or not at all.
async with session.begin():
    user = await UserService(session).create(user_dto)
    await ProfileService(session).create(profile_dto_for(user))
```

With **`autocommit = False`** the service never calls **`commit()`** or **`rollback()`** — that is the caller's responsibility (a request-level dependency, a consumer handler, a scheduler tick).

### Upload extra

Install **`approck-services[upload]`** (pulls in **`aioboto3`**). Import **`approck_services.integrations.upload.BaseUploadService`**.

`BaseUploadService` is constructed with AWS-style credentials, **`region_name`**, **`bucket`**, and optional **`endpoint_url`** (MinIO, Cloudflare R2, other S3-compatible APIs). It exposes:

- **`upload_from_bytes(key, body, content_type=None)`** — upload raw bytes.
- **`upload_from_file(key, file_, content_type=None)`** — upload from a binary file-like object.
- **`upload_from_url(url, key=None, prefix=None)`** — download via **`urllib`** (synchronous fetch) then upload; if **`key`** is omitted, the last path segment of the URL is used, optionally prefixed.

If **`endpoint_url`** is set, upload methods return a string URL **`{endpoint_url}/{bucket}/{quoted_key}`**. If it is **`None`** (typical AWS), they return **`None`** — build the public URL in your app if needed.

```python
import os

from approck_services.integrations.upload import BaseUploadService


class AppUploadService(BaseUploadService):
    def __init__(self) -> None:
        super().__init__(
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
            bucket=os.environ["S3_BUCKET"],
            endpoint_url=os.environ.get("S3_ENDPOINT_URL"),  # set for MinIO / R2; omit for AWS
        )


async def save_avatar(service: AppUploadService, user_id: int, png: bytes) -> str | None:
    return await service.upload_from_bytes(
        key=f"avatars/{user_id}.png",
        body=png,
        content_type="image/png",
    )


async def mirror_remote(service: AppUploadService, image_url: str) -> str | None:
    return await service.upload_from_url(
        image_url,
        prefix="imports/",
    )
```

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, tests, and pull requests.

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE).
