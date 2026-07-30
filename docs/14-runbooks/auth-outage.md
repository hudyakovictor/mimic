# Runbook: Auth outage

## Симптомы
- 401 на все запросы.
- Login endpoint 5xx.
- OIDC provider недоступен.

## Диагностика

```bash
# 1. Проверить OIDC
curl -i https://<oidc-host>/.well-known/openid-configuration

# 2. Проверить JWT_SECRET
kubectl -n mimicguard get secret api-secrets -o jsonpath='{.data.JWT_SECRET}' | base64 -d

# 3. Проверить clock skew
date
# Сравнить с NTP
```

## Типовые причины
1. **OIDC provider down** — Keycloak / Auth0 / Okta outage.
2. **Wrong JWT_SECRET после deploy** — старый secret не в env.
3. **Clock skew** — JWT exp в прошлом.

## Митигация

1. **OIDC down:** переключить в dev-режим (HS256) — только system_admin, с audit-записью.
2. **Wrong secret:** откатить deploy.
3. **Clock skew:** ntpdate / chronyc tracking, рестарт API.

## Предотвращение
- Cache валидных токенов на 60 сек в API, чтобы brief OIDC blip не ломал auth.
- Мониторинг на 401 rate spike.
- Pre-deploy hook: проверка JWT_SECRET непустой.
