# Module 15: Security

**Путь:** `services/api/app/security/`

## Файлы

### `jwt.py`
```python
"""
MG-STUB: реализовать:
- encode_access_token(user_id, tenant_id, roles, ttl=15min) -> str
    payload: {sub, tid, roles, iat, exp, aud, iss, jti}
    HS256 в dev, RS256 в production (public key from JWKS)
- encode_refresh_token(user_id, jti) -> str (24h TTL, rotation_id stored in Redis)
- decode_token(token) -> claims dict
    - verify aud, iss, exp
    - на ошибку raise ApiError(401, 'invalid_token')
- revoke_token(jti, ttl): SET jti:blacklisted EX ttl
"""
```

### `passwords.py`
```python
"""
MG-STUB: реализовать:
- hash_password(plain) -> str (bcrypt cost=12)
- verify_password(plain, hashed) -> bool
"""
```

### `rbac.py`
```python
"""
MG-STUB: реализовать:
- Permission = Enum:
    USER_READ, USER_WRITE, ROLE_ASSIGN,
    ASSET_READ, ASSET_WRITE, ASSET_DOWNLOAD,
    VIDEO_READ, BIOMETRIC_EXPORT,
    SUBJECT_READ, SUBJECT_WRITE, SUBJECT_DELETE,
    JOB_READ, JOB_WRITE, JOB_RETRY,
    DECISION_READ, REVIEW_WRITE,
    MODEL_READ, MODEL_PROMOTE, MODEL_ROLLBACK,
    BASELINE_READ, BASELINE_REBUILD,
    AUDIT_READ, AUDIT_EXPORT,
    SYSTEM_ADMIN
- RolePermissionMatrix: dict[Role, set[Permission]]
- require_permission(perm): FastAPI dependency factory
    - читает current_user.permissions
    - если нет perm → raise PermissionDeniedError
- has_role(user, *roles) -> bool
"""
```

### `tenant_context.py`
```python
"""
MG-STUB: реализовать:
- TenantContext middleware: извлекает tenant_id из JWT claim `tid`,
  кладёт в contextvar.
- get_current_tenant_id() -> UUID
- with_tenant(session, tenant_id) -> session context manager
"""
```

### `audit_context.py`
```python
"""
MG-STUB: реализовать:
- AuditContext: собирает текущий request_id, actor_id, ip, user_agent.
- attach_to_request(request): middleware, кладёт в contextvar.
"""
```

## Security middleware order
1. `RequestIdMiddleware` (внешний)
2. `CORSMiddleware`
3. `AuditContextMiddleware` (после auth, но в одном request scope)
4. `RateLimitMiddleware`
5. Endpoint handler

## Token rotation policy
- Access token TTL: 15 мин.
- Refresh token TTL: 24 ч, rotation mandatory on use.
- Refresh blacklist: 7 дней после expiry.

## Password policy
- Min length 12.
- Common password check (HIBP API или локальный список top 10k).
- Rate limit: 5 login attempts/min/IP + 20/hour/user.
