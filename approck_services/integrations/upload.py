import io
import os.path
import typing
import urllib.parse
import urllib.request

import aioboto3

from approck_services.base import BaseService


class BaseUploadService(BaseService):
    def __init__(
        self,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        region_name: str,
        bucket: str,
        endpoint_url: typing.Optional[str] = None,
    ) -> None:
        super().__init__()

        self.session = aioboto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
        )

        self.bucket = bucket
        self.endpoint_url = endpoint_url

    async def upload_from_bytes(
        self,
        key: str,
        body: bytes,
        content_type: typing.Optional[str] = None,
    ) -> str | None:
        with io.BytesIO(body) as spfp:
            return await self.upload_from_file(key=key, file_=spfp, content_type=content_type)

    async def upload_from_file(
        self,
        key: str,
        file_: typing.BinaryIO,
        content_type: typing.Optional[str] = None,
    ) -> str | None:
        extra_args = {}
        if content_type is not None:
            extra_args["ContentType"] = content_type

        async with self.session.client("s3", endpoint_url=self.endpoint_url) as s3:
            await s3.upload_fileobj(file_, self.bucket, key, ExtraArgs=extra_args if extra_args else None)

        if self.endpoint_url is not None:
            return f"{self.endpoint_url}/{self.bucket}/{urllib.parse.quote(key)}"

        return None

    async def upload_from_url(
        self, url: str, key: typing.Optional[str] = None, prefix: typing.Optional[str] = None
    ) -> str | None:
        target_key = key

        if target_key is None:
            filename = os.path.basename(urllib.parse.urlparse(url).path)
            target_key = f"{prefix}{filename}" if prefix else filename

        with urllib.request.urlopen(url) as file_:
            return await self.upload_from_file(
                key=target_key, file_=file_, content_type=file_.getheader("Content-Type")
            )
