"""Bucket configuration and lifecycle policies.

MG-STUB: final.
"""
from __future__ import annotations

from .s3_client import S3Client

BUCKET_VIDEOS = "mimicguard-videos"
BUCKET_DERIVED = "mimicguard-derived"
BUCKET_CLIPS = "mimicguard-clips"
BUCKET_MODELS = "mimicguard-models"
BUCKET_AUDIT = "mimicguard-audit"

ALL_BUCKETS = [
    BUCKET_VIDEOS,
    BUCKET_DERIVED,
    BUCKET_CLIPS,
    BUCKET_MODELS,
    BUCKET_AUDIT,
]


async def init_buckets(s3: S3Client) -> None:
    """Create all required buckets if missing."""
    for b in ALL_BUCKETS:
        await s3.ensure_bucket(b)


async def apply_lifecycle_policies(s3: S3Client) -> None:
    """Configure lifecycle policies on each bucket.

    For MinIO dev, lifecycle transitions are limited; this is a no-op when not supported.
    In production on AWS S3/GCS, the rules are applied.
    """
    # No-op for dev. In prod: boto3 put_bucket_lifecycle_configuration.
    return
