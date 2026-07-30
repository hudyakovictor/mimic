# Module 10: FastAPI composition root

**Путь:** `services/api/app/`
**Назначение:** Composition root, middlewares, error handling, OpenAPI customization.

## Файлы

### `app/main.py`
```python
"""
MG-STUB: реализовать полный composition root.
Должен:
- Создать FastAPI instance с метаданными.
- Подключить CORS middleware (только whitelisted origins).
- Подключить request_id middleware (X-Request-ID header → contextvar).
- Подключить structlog JSON middleware.
- Подключить OpenTelemetry middleware.
- Подключить global exception handlers:
    - RequestValidationError → 422 с field_errors.
    - ApiError → status_code, body {code, message, correlationId}.
    - SQLAlchemyError → 500, generic message, log details.
    - Exception → 500, generic, log full stack.
- Подключить routers: auth, assets, jobs, subjects, words, decisions, reviews, models, audit, system.
- На startup: проверить подключение к PostgreSQL/Redis/MinIO, прогреть кеши.
- На shutdown: drain in-flight requests, закрыть connection pools.
"""
```

### `app/middlewares.py`
- `RequestIdMiddleware` — извлекает `X-Request-ID` или генерит UUID4, кладёт в contextvar.
- `LoggingMiddleware` — логирует request/response с duration, status, request_id, user_id (если есть).
- `CORSMiddleware` — белый список origins из settings.
- `RateLimitMiddleware` — token bucket per user_id (10 RPS default).

### `app/errors.py`
- `ApiError` — base exception с `status_code`, `code`, `message`, `field_errors`.
- Подклассы: `NotFoundError`, `PermissionDeniedError`, `ValidationError`, `ConflictError`, `RateLimitError`.
- `register_exception_handlers(app)` — регистрирует handlers для ApiError и FastAPI exceptions.

### `app/settings.py`
- Pydantic Settings: `DATABASE_URL`, `REDIS_URL`, `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `JWT_SECRET`, `JWT_ALG`, `JWT_AUDIENCE`, `JWT_ISSUER`, `ACCESS_TOKEN_TTL`, `REFRESH_TOKEN_TTL`, `CORS_ORIGINS`, `RATE_LIMIT_RPS`, `MEDIA_ROOT_PATH`, `MAX_UPLOAD_BYTES`, `MAX_VIDEO_DURATION_S`, `LOG_LEVEL`, `ENV`.
- Все secrets — через `SecretStr`.

### `app/observability.py`
- `configure_logging(level)` — structlog JSON renderer.
- `configure_metrics(app)` — prometheus_client Instrumentator + custom collectors.
- `configure_tracing(app)` — OpenTelemetry FastAPIInstrumentor, OTLP exporter.

### `app/dependencies.py`
- `get_db()` — async session per request.
- `get_redis()` — connection pool.
- `get_s3()` — boto3 client.
- `get_current_user(token: str = Depends(oauth2_scheme))` — decode JWT, load user from DB.
- `require_role(*roles)` — factory.
- `get_tenant_id(current_user)` — из JWT claim.

## Signals
- `app_started_at` — gauge.
- `db_pool_in_use` — gauge.
- `redis_pool_in_use` — gauge.
- `http_requests_total{path, method, status}` — counter.
- `http_request_duration_seconds{path, method, status}` — histogram.

## Что НЕ делается здесь
- Никаких бизнес-решений.
- Никаких SQL-запросов напрямую.
- Никаких обращений к S3/Redis.
