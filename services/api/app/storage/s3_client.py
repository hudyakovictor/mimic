"""S3 client wrapper.

MG-STUB: final — uses boto3 in a thread executor. All operations are async.
For local dev, the endpoint points to MinIO.
"""
from __future__ import annotations

import asyncio
from functools import partial
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from ..observability import get_logger
from ..settings import Settings

log = get_logger(__name__)


class S3Client:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key.get_secret_value(),
            aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
            region_name=settings.s3_region,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    async def _run(self, fn, *args, **kwargs) -> Any:
        return await asyncio.get_event_loop().run_in_executor(None, partial(fn, *args, **kwargs))

    async def head_object(self, bucket: str, key: str) -> dict | None:
        try:
            return await self._run(self._client.head_object, Bucket=bucket, Key=key)
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return None
            raise

    async def get_object(self, bucket: str, key: str) -> bytes:
        resp = await self._run(self._client.get_object, Bucket=bucket, Key=key)
        return resp["Body"].read()

    async def put_object(
        self, bucket: str, key: str, body: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        resp = await self._run(
            self._client.put_object, Bucket=bucket, Key=key, Body=body, ContentType=content_type
        )
        return resp.get("ETag", "")

    async def delete_object(self, bucket: str, key: str) -> None:
        try:
            await self._run(self._client.delete_object, Bucket=bucket, Key=key)
        except ClientError as e:
            log.warning("s3_delete_failed", bucket=bucket, key=key, error=str(e))

    async def generate_presigned_put(
        self,
        bucket: str,
        key: str,
        content_type: str,
        content_length_range: tuple[int, int],
        ttl: int | None = None,
    ) -> dict:
        ttl = ttl or self.settings.s3_presigned_url_ttl
        conditions: list[Any] = [
            {"Content-Type": content_type},
            ["content-length-range", content_length_range[0], content_length_range[1]],
        ]
        presigned = await self._run(
            self._client.generate_presigned_post,
            Bucket=bucket,
            Key=key,
            Conditions=conditions,
            ExpiresIn=ttl,
        )
        return {
            "url": presigned["url"],
            "fields": {k: str(v) for k, v in presigned["fields"].items()},
        }

    async def generate_presigned_get(
        self, bucket: str, key: str, ttl: int | None = None
    ) -> str:
        ttl = ttl or self.settings.s3_presigned_url_ttl
        return await self._run(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=ttl,
        )

    async def ensure_bucket(self, bucket: str) -> None:
        try:
            await self._run(self._client.head_bucket, Bucket=bucket)
        except ClientError:
            await self._run(self._client.create_bucket, Bucket=bucket)
            log.info("s3_bucket_created", bucket=bucket)

    async def upload_file(self, bucket: str, key: str, file_path: str) -> str:
        def _do() -> str:
            self._client.upload_file(file_path, bucket, key)
            return key

        return await self._run(_do)

    async def download_file(self, bucket: str, key: str, file_path: str) -> None:
        def _do() -> None:
            self._client.download_file(bucket, key, file_path)

        await self._run(_do)


_client_singleton: S3Client | None = None


def get_s3_client(settings: Settings | None = None) -> S3Client:
    global _client_singleton
    if _client_singleton is None:
        from ..settings import get_settings as _gs

        _client_singleton = S3Client(settings or _gs())
    return _client_singleton
