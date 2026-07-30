"""Application settings, loaded from environment variables via Pydantic Settings.

MG-STUB: final — uses pydantic-settings. All values are read-only; mutations
require process restart. Secrets are typed as SecretStr to prevent accidental
leakage in logs.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # General
    env: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"
    service_name: str = "mimicguard"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    api_base_url: str = "http://localhost:8080"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    rate_limit_rps: int = 10

    # Database
    database_url: str = "postgresql+asyncpg://mimicguard:mimicguard@localhost:5432/mimicguard"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_broker_url: str = "redis://localhost:6379/1"

    # S3 / MinIO
    s3_endpoint: str = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_access_key: SecretStr = SecretStr("mimicguard")
    s3_secret_key: SecretStr = SecretStr("change-me-now")
    s3_bucket_videos: str = "mimicguard-videos"
    s3_bucket_derived: str = "mimicguard-derived"
    s3_bucket_clips: str = "mimicguard-clips"
    s3_bucket_models: str = "mimicguard-models"
    s3_bucket_audit: str = "mimicguard-audit"
    s3_presigned_url_ttl: int = 900

    # Security
    jwt_secret: SecretStr = SecretStr("dev-secret-change-me")
    jwt_alg: Literal["HS256", "RS256"] = "HS256"
    jwt_audience: str = "mimicguard-api"
    jwt_issuer: str = "mimicguard"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 86400

    # Upload limits
    max_upload_bytes: int = 1_073_741_824
    max_video_duration_seconds: int = 1800

    # MediaPipe
    mediapipe_model_path: str | None = None
    mediapipe_min_confidence: float = 0.5

    # ASR
    asr_model_size: Literal["tiny", "base", "small", "medium", "large-v3"] = "small"
    asr_device: Literal["auto", "cpu", "cuda"] = "auto"
    asr_compute_type: str = "int8"

    # Quality thresholds
    quality_min_frames: int = 15
    quality_min_mean_confidence: float = 0.72
    quality_max_gap_ms: int = 180
    quality_max_abs_yaw: float = 45.0
    quality_min_score: float = 0.55

    # Decision thresholds
    decision_risk_consistent_max: float = 0.35
    decision_risk_suspicious_min: float = 0.65
    phrase_baseline_min_samples: int = 3
    phrase_baseline_mature_samples: int = 10
    phrase_template_max_samples: int = 50

    # Outbox
    outbox_poll_interval_ms: int = 200
    outbox_batch_size: int = 200
    outbox_max_attempts: int = 10

    # Worker
    worker_time_limit_default: int = 300_000
    worker_retry_default: int = 3

    # Observability
    otel_exporter_otlp_endpoint: str | None = None
    prometheus_metrics_path: str = "/metrics"

    # Default admin
    default_admin_email: str = "admin@local"
    default_admin_password: str = "change-me-now-12chars"
    default_tenant_slug: str = "default"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return process-wide settings singleton."""
    return Settings()
