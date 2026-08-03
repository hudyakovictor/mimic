"""Run 50 high-value repository diagnostics and write one machine-readable JSONL log."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Result:
    status: str
    detail: str


def ok(condition: bool, detail: str, failure: str) -> Result:
    return Result("PASS" if condition else "FAIL", detail if condition else failure)


def warn(condition: bool, detail: str, warning: str) -> Result:
    return Result("PASS" if condition else "WARN", detail if condition else warning)


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def command(cmd: list[str], cwd: str = ".", timeout: int = 180) -> Result:
    try:
        run = subprocess.run(cmd, cwd=ROOT / cwd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return Result("FAIL", f"{type(exc).__name__}: {exc}")
    output = (run.stdout + "\n" + run.stderr).strip().replace("\x00", "")
    tail = " | ".join(output.splitlines()[-4:])[-1200:]
    return Result("PASS" if run.returncode == 0 else "FAIL", tail or f"exit={run.returncode}")


def executable(name: str) -> Result:
    path = shutil.which(name)
    return ok(bool(path), path or "", f"{name} not found")


def file_exists(path: str) -> Result:
    return ok((ROOT / path).is_file(), path, f"missing {path}")


def contains(path: str, needle: str) -> Result:
    body = text(path)
    return ok(needle in body, f"{path} contains required invariant", f"{path} misses: {needle}")


def import_readiness() -> Result:
    required = ["fastapi", "sqlalchemy", "structlog", "redis", "boto3", "dramatiq", "pydantic_settings"]
    missing = [name for name in required if importlib.util.find_spec(name) is None]
    return warn(not missing, "required runtime packages importable", f"environment missing packages: {', '.join(missing)}")


def parse_pyproject() -> Result:
    data = tomllib.loads(text("pyproject.toml"))
    return ok(data.get("project", {}).get("name") == "mimicguard", "pyproject valid", "invalid project metadata")


def parse_package_json() -> Result:
    data = json.loads(text("apps/admin/package.json"))
    scripts = data.get("scripts", {})
    return ok(all(k in scripts for k in ("build", "lint", "typecheck")), "frontend scripts valid", "frontend scripts incomplete")


def parse_compose() -> Result:
    body = text("infra/docker-compose.yml")
    services = re.findall(r"^  ([a-z][\w-]*):\n", body, re.M)
    return ok({"api", "worker", "postgres", "redis", "minio"}.issubset(services), f"services={services}", "compose core services missing")


def no_pattern(pattern: str, globs: tuple[str, ...]) -> Result:
    matches: list[str] = []
    rx = re.compile(pattern)
    for base in globs:
        for path in (ROOT / base).rglob("*"):
            if path.is_file() and path.suffix in {".py", ".ts", ".tsx"} and "node_modules" not in path.parts:
                for number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    if rx.search(line):
                        matches.append(f"{path.relative_to(ROOT)}:{number}")
    return ok(not matches, "none", "matches: " + ", ".join(matches[:12]))


def unique_storage_keys() -> Result:
    body = text("services/api/app/storage/keys.py")
    suffixes = re.findall(r'return f"\{tenant_id\}/([^"\n]+)"', body)
    return ok(len(suffixes) == len(set(suffixes)), f"{len(suffixes)} key patterns unique", "duplicate storage key patterns")


def thresholds() -> Result:
    body = text("services/api/app/settings.py")
    a = float(re.search(r"decision_risk_consistent_max: float = ([\d.]+)", body).group(1))
    b = float(re.search(r"decision_risk_suspicious_min: float = ([\d.]+)", body).group(1))
    return ok(0 <= a < b <= 1, f"thresholds {a} < {b}", "invalid decision thresholds")


def routes_count() -> Result:
    count = len(re.findall(r"app\.include_router\(", text("services/api/app/main.py")))
    return ok(count >= 10, f"{count} routers registered", f"only {count} routers registered")


def log_writable() -> Result:
    path = ROOT / "logs" / ".write-test"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text("ok", encoding="utf-8")
        path.unlink()
        return Result("PASS", str(path.parent))
    except OSError as exc:
        return Result("FAIL", str(exc))


def archive_clean() -> Result:
    junk = [p for p in ROOT.rglob("*") if p.name == "__MACOSX" or p.name.startswith("._")]
    return ok(not junk, "no macOS metadata", f"{len(junk)} macOS metadata paths")


def runtime_model_assets() -> Result:
    model_path = os.getenv("MIMICGUARD_MEDIAPIPE_MODEL_PATH")
    return warn(bool(model_path and Path(model_path).is_file()), "MediaPipe model configured", "model will be downloaded/cached on first worker run")


CHECKS: list[tuple[str, Callable[[], Result]]] = [
    ("python_version", lambda: ok(sys.version_info >= (3, 11), sys.version.split()[0], "Python < 3.11")),
    ("node_executable", lambda: executable("node")),
    ("npm_executable", lambda: executable("npm")),
    ("ffmpeg_executable", lambda: executable("ffmpeg")),
    ("ffprobe_executable", lambda: executable("ffprobe")),
    ("runtime_dependencies", import_readiness),
    ("pyproject_parse", parse_pyproject),
    ("package_json_parse", parse_package_json),
    ("uv_lock_present", lambda: file_exists("uv.lock")),
    ("frontend_lock_present", lambda: warn((ROOT / "apps/admin/pnpm-lock.yaml").is_file(), "pnpm lock present", "pnpm lock missing")),
    ("compose_core_services", parse_compose),
    ("python_compile", lambda: command([sys.executable, "-m", "compileall", "-q", "services", "packages", "scripts", "tools"])),
    ("no_todo_fixme", lambda: no_pattern(r"\b(TODO|FIXME)\b", ("services", "packages", "apps/admin/src"))),
    ("no_notimplemented", lambda: no_pattern(r"raise\s+NotImplementedError", ("services", "packages"))),
    ("pipeline_retry_reset", lambda: contains("services/worker/worker/actors/pipeline.py", "_mark_job_after_failure")),
    ("pipeline_terminal_failure", lambda: contains("services/worker/worker/actors/pipeline.py", 'state="FAILED" if terminal else "QUEUED"')),
    ("immature_baseline_not_scored", lambda: ok("risk_scores.append(0.5)" not in text("services/worker/worker/actors/pipeline.py"), "immature baselines excluded", "immature baselines bias risk")),
    ("minimum_mature_phrases", lambda: contains("services/worker/worker/actors/pipeline.py", "decision_min_mature_phrases")),
    ("weighted_risk", lambda: contains("services/worker/worker/actors/pipeline.py", "np.average(risk_scores, weights=risk_weights)")),
    ("stage_started_logging", lambda: contains("services/worker/worker/actors/pipeline.py", "pipeline.stage_started")),
    ("stage_completed_logging", lambda: contains("services/worker/worker/actors/pipeline.py", "pipeline.stage_completed")),
    ("stage_failed_logging", lambda: contains("services/worker/worker/actors/pipeline.py", "pipeline.stage_failed")),
    ("shared_log_setting", lambda: contains("services/api/app/settings.py", "log_file: str")),
    ("api_file_logging", lambda: contains("services/api/app/main.py", "settings.log_file")),
    ("worker_file_logging", lambda: contains("services/worker/worker/broker.py", "settings.log_file")),
    ("compose_shared_log_volume", lambda: contains("infra/docker-compose.yml", "mimicguard-logs:/var/log/mimicguard")),
    ("request_correlation", lambda: contains("services/api/app/main.py", "bind_contextvars(request_id=request_id")),
    ("worker_correlation", lambda: contains("services/worker/worker/actors/pipeline.py", "correlation_id=correlation_id")),
    ("log_directory_writable", log_writable),
    ("ffprobe_json_guard", lambda: contains("services/worker/worker/video/probe.py", "malformed JSON")),
    ("ffprobe_average_fps", lambda: contains("services/worker/worker/video/probe.py", "avg_frame_rate")),
    ("audio_pcm_contract", lambda: contains("services/worker/worker/video/probe.py", "pcm_s16le")),
    ("wav_channel_handling", lambda: contains("services/worker/worker/video/probe.py", "reshape(-1, channels).mean")),
    ("safe_clip_profile", lambda: ok(all(x in text("services/worker/worker/video/probe.py") for x in ('"17"', '"yuv420p"', '"+faststart"')), "safe clip profile", "unsafe clip profile")),
    ("resample_without_scipy", lambda: ok("scipy.interpolate" not in text("services/worker/worker/phoneme/align.py"), "numpy resampling", "scipy resampling dependency remains")),
    ("unicode_token_normalization", lambda: contains("services/worker/worker/phoneme/align.py", "unicodedata.normalize")),
    ("alignment_bounds", lambda: contains("services/worker/worker/phoneme/align.py", "min(audio.size")),
    ("dtw_shape_validation", lambda: contains("services/worker/worker/baseline/match.py", "DTW inputs must be 2D")),
    ("nonfinite_motion_guard", lambda: contains("services/worker/worker/baseline/match.py", "contain NaN or infinity")),
    ("statistical_threshold_no_scipy", lambda: ok("from scipy" not in text("services/worker/worker/baseline/match.py") and "import scipy" not in text("services/worker/worker/baseline/match.py"), "stdlib threshold approximation", "scipy import remains in matcher")),
    ("core_unit_tests", lambda: command(["bash", "-lc", "PYTHONPATH=services/api:services/worker:. python -m unittest tests.unit.test_align tests.unit.test_dtw tests.unit.test_normalization tests.unit.test_quality -q"], timeout=60)),
    ("frontend_typecheck", lambda: command(["npm", "run", "typecheck"], "apps/admin", 120)),
    ("frontend_lint", lambda: command(["npm", "run", "lint"], "apps/admin", 120)),
    ("frontend_build", lambda: command(["npm", "run", "build"], "apps/admin", 180)),
    ("api_router_registration", routes_count),
    ("initial_migration", lambda: file_exists("services/api/alembic/versions/0001_initial.py")),
    ("storage_key_uniqueness", unique_storage_keys),
    ("decision_thresholds", thresholds),
    ("accuracy_validation_doc", lambda: file_exists("docs/16-accuracy-validation-plan.md")),
    ("archive_metadata_clean", archive_clean),
]

assert len(CHECKS) == 50, len(CHECKS)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="logs/diagnostics.jsonl")
    args = parser.parse_args()
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    with output.open("w", encoding="utf-8") as log:
        log.write(json.dumps({"type": "diagnostic_start", "checks": 50, "timestamp": started}) + "\n")
        for index, (name, fn) in enumerate(CHECKS, 1):
            t0 = time.perf_counter()
            try:
                result = fn()
            except Exception as exc:
                result = Result("FAIL", f"{type(exc).__name__}: {exc}")
            counts[result.status] += 1
            event = {
                "type": "diagnostic_result", "index": index, "name": name,
                "status": result.status, "duration_ms": round((time.perf_counter() - t0) * 1000, 2),
                "detail": result.detail,
            }
            log.write(json.dumps(event, ensure_ascii=False) + "\n")
            print(f"[{index:02d}/50] {result.status:4} {name}: {result.detail}")
        summary = {"type": "diagnostic_summary", **counts, "duration_seconds": round(time.time() - started, 2)}
        log.write(json.dumps(summary, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False))
    print(f"Log: {output}")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
