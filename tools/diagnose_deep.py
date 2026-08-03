"""Second-pass suite: 50 additional security, retry, isolation and deployment checks."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Result:
    status: str
    detail: str


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def present(path: str, *needles: str) -> Result:
    body = source(path)
    missing = [needle for needle in needles if needle not in body]
    return Result("PASS", f"{path}: {len(needles)} invariants") if not missing else Result("FAIL", f"missing: {missing}")


def absent(path: str, *needles: str) -> Result:
    body = source(path)
    found = [needle for needle in needles if needle in body]
    return Result("PASS", f"{path}: forbidden patterns absent") if not found else Result("FAIL", f"found: {found}")


def cmd(command: list[str], cwd: str = ".", timeout: int = 180) -> Result:
    try:
        run = subprocess.run(command, cwd=ROOT / cwd, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:
        return Result("FAIL", f"{type(exc).__name__}: {exc}")
    output = (run.stdout + "\n" + run.stderr).strip().splitlines()
    tail = " | ".join(output[-4:])[-1400:] if output else f"exit={run.returncode}"
    return Result("PASS" if run.returncode == 0 else "FAIL", tail)


def order(path: str, first: str, second: str) -> Result:
    body = source(path)
    a, b = body.find(first), body.find(second)
    return Result("PASS", f"{first!r} precedes {second!r}") if 0 <= a < b else Result("FAIL", f"invalid order: {a}, {b}")


CHECKS: list[tuple[str, Callable[[], Result]]] = [
    ("production_security_validator", lambda: present("services/api/app/settings.py", "validate_production_security", "self.env != \"production\"")),
    ("production_jwt_strength", lambda: present("services/api/app/settings.py", "len(jwt_value) < 32")),
    ("production_cors_guard", lambda: present("services/api/app/settings.py", "Wildcard CORS is forbidden")),
    ("production_default_secret_guard", lambda: present("services/api/app/settings.py", "Production S3_SECRET_KEY", "Production DEFAULT_ADMIN_PASSWORD")),
    ("jwt_access_type_claim", lambda: present("services/api/app/security/jwt_service.py", 'claims["typ"] = "access"')),
    ("jwt_access_type_enforced", lambda: present("services/api/app/security/current_user.py", 'expect_type="access"')),
    ("revoked_access_rejected", lambda: order("services/api/app/security/current_user.py", "except Exception:\n        revoked = False", "if revoked:\n        raise UnauthorizedError")),
    ("malformed_claims_rejected", lambda: present("services/api/app/security/current_user.py", "Token has invalid subject claims")),
    ("rate_limit_not_swallowed", lambda: order("services/api/app/services/auth.py", "except Exception as e:", "else:\n                if count > 5")),
    ("duplicate_login_identity_safe", lambda: present("services/api/app/services/auth.py", "if len(candidates) != 1")),
    ("revoked_refresh_rejected", lambda: present("services/api/app/services/auth.py", 'raise UnauthorizedError("Refresh token revoked")')),
    ("refresh_tenant_binding", lambda: present("services/api/app/services/auth.py", "user.tenant_id != tenant_id")),
    ("browser_tokens_session_scoped", lambda: present("apps/admin/src/stores/auth.ts", "createJSONStorage(() => sessionStorage)", "sessionStorage.setItem")),
    ("api_reads_session_token", lambda: present("apps/admin/src/api/client.ts", "sessionStorage.getItem('access_token')")),
    ("repository_list_tenant_scoped", lambda: present("services/api/app/repositories/base.py", 'stmt = stmt.where(getattr(self.model, "tenant_id") == self.tenant_id)')),
    ("repository_count_tenant_scoped", lambda: present("services/api/app/repositories/base.py", "async def count", 'getattr(self.model, "tenant_id") == self.tenant_id')),
    ("cursor_timestamp_parsed", lambda: present("services/api/app/repositories/base.py", "datetime.fromisoformat")),
    ("cursor_keyset_tie_break", lambda: present("services/api/app/repositories/base.py", "or_(", "order_col == c_created")),
    ("decision_list_tenant_scoped", lambda: present("services/api/app/repositories/decisions.py", "Decision.tenant_id == self.tenant_id")),
    ("review_list_tenant_scoped", lambda: present("services/api/app/repositories/decisions.py", "Review.tenant_id == self.tenant_id")),
    ("stage_list_tenant_scoped", lambda: present("services/api/app/repositories/jobs.py", "JobStage.tenant_id == self.tenant_id")),
    ("stage_attempt_from_job", lambda: present("services/worker/worker/actors/db.py", "actual_attempt = int", "else job.attempt")),
    ("pipeline_uses_actual_attempt", lambda: present("services/worker/worker/actors/pipeline.py", "actual_attempt = row.attempt", "_StageCtx(job_id, name, actual_attempt)")),
    ("retry_has_terminal_state", lambda: present("services/worker/worker/actors/pipeline.py", 'state="FAILED" if terminal else "QUEUED"')),
    ("no_audio_is_explicit", lambda: present("services/worker/worker/actors/pipeline.py", "NO_AUDIO_STREAM")),
    ("outbox_attempt_cap_query", lambda: present("services/api/app/events/outbox.py", "OutboxEvent.attempts < max_attempts")),
    ("publisher_accepts_attempt_cap", lambda: present("services/api/app/events/publisher.py", "max_attempts: int = 10", "max_attempts=max_attempts")),
    ("relay_passes_attempt_cap", lambda: present("services/api/app/main.py", "max_attempts=settings.outbox_max_attempts")),
    ("s3_uses_running_loop", lambda: present("services/api/app/storage/s3_client.py", "asyncio.get_running_loop()")),
    ("s3_body_read_offloaded", lambda: present("services/api/app/storage/s3_client.py", "await self._run(body.read)")),
    ("s3_body_closed", lambda: present("services/api/app/storage/s3_client.py", "finally:\n            body.close()")),
    ("upload_mime_allowlist", lambda: present("services/api/app/services/assets.py", "allowed_mimes", "Unsupported video MIME type")),
    ("upload_runtime_size_limit", lambda: present("services/api/app/services/assets.py", "size_bytes > get_settings().max_upload_bytes")),
    ("upload_extension_sanitized", lambda: present("services/api/app/services/assets.py", 're.sub(r"[^a-z0-9]"', "Unsupported video file extension")),
    ("invalid_video_fails_closed", lambda: present("services/api/app/services/assets.py", "Uploaded object is not a valid video")),
    ("server_metadata_authoritative", lambda: present("services/api/app/services/assets.py", "duration_ms = info.duration_ms", "width = info.width", "fps = info.fps")),
    ("redirect_ssrf_revalidation", lambda: present("services/api/app/services/assets.py", "await validate_public_media_url(current_url)")),
    ("redirect_limit", lambda: present("services/api/app/services/assets.py", "for _redirect in range(6)", "Too many redirects")),
    ("streaming_download_limit", lambda: present("services/api/app/services/assets.py", "if downloaded > max_bytes")),
    ("mediapipe_model_failure_actionable", lambda: present("services/worker/worker/landmarks/extract.py", "MIMICGUARD_MEDIAPIPE_MODEL_PATH", "MediaPipe model is unavailable")),
    ("model_artifact_file_closed", lambda: present("packages/landmark_engine/adapters/model_scorer.py", 'with open(baseline_uri, "rb") as stream')),
    ("motion_nonfinite_guard", lambda: present("services/worker/worker/baseline/match.py", "contain NaN or infinity")),
    ("api_image_has_no_dev_ml_extras", lambda: absent("infra/Dockerfile.api", '".[landmarks,asr,youtube,dev]"')),
    ("api_docker_pipefail", lambda: present("infra/Dockerfile.api", 'SHELL ["/bin/bash", "-o", "pipefail", "-c"]')),
    ("worker_docker_pipefail", lambda: present("infra/Dockerfile.worker", 'SHELL ["/bin/bash", "-o", "pipefail", "-c"]')),
    ("api_container_healthcheck", lambda: present("infra/docker-compose.yml", "http://localhost:8080/health/ready")),
    ("worker_waits_for_healthy_api", lambda: present("infra/docker-compose.yml", "condition: service_healthy")),
    ("python_full_compile", lambda: cmd([sys.executable, "-m", "compileall", "-q", "services", "packages", "scripts", "tools"])),
    ("core_algorithm_regression", lambda: cmd(["bash", "-lc", "PYTHONPATH=services/api:services/worker:. python -m unittest tests.unit.test_align tests.unit.test_dtw tests.unit.test_normalization tests.unit.test_quality -q"], timeout=60)),
    ("frontend_quality_gate", lambda: cmd(["bash", "-lc", "npm run typecheck && npm run lint && npm run build"], "apps/admin", 180)),
]

assert len(CHECKS) == 50, len(CHECKS)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="logs/diagnostics-deep.jsonl")
    args = parser.parse_args()
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    started = time.time()
    with output.open("w", encoding="utf-8") as log:
        log.write(json.dumps({"type": "deep_diagnostic_start", "checks": 50, "timestamp": started}) + "\n")
        for index, (name, check) in enumerate(CHECKS, 1):
            tick = time.perf_counter()
            try:
                result = check()
            except Exception as exc:
                result = Result("FAIL", f"{type(exc).__name__}: {exc}")
            counts[result.status] += 1
            event = {"type": "deep_diagnostic_result", "index": index, "name": name, "status": result.status, "duration_ms": round((time.perf_counter() - tick) * 1000, 2), "detail": result.detail}
            log.write(json.dumps(event, ensure_ascii=False) + "\n")
            print(f"[{index:02d}/50] {result.status:4} {name}: {result.detail}")
        summary = {"type": "deep_diagnostic_summary", **counts, "duration_seconds": round(time.time() - started, 2)}
        log.write(json.dumps(summary, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False))
    print(f"Log: {output}")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
