from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import time
import zlib
from dataclasses import dataclass
from typing import Any, Protocol

from .models import ForecastRow, canonical_json


@dataclass(frozen=True)
class ExecutionResult:
    rows: list[ForecastRow]
    duration_seconds: float
    backend: str
    request_sha256: str
    stderr: str = ""


class Executor(Protocol):
    name: str

    def execute(self, request: dict[str, Any]) -> ExecutionResult: ...

    def policy(self) -> dict[str, Any]: ...


def _parse_output(output: str) -> list[ForecastRow]:
    if len(output.encode()) > 5_000_000:
        raise RuntimeError("worker output exceeded 5 MB")
    value = json.loads(output)
    if set(value) != {"schema_version", "forecasts"} or value["schema_version"] != 1:
        raise ValueError("worker response schema mismatch")
    return [ForecastRow.from_dict(row) for row in value["forecasts"]]


class LocalExecutor:
    name = "local-subprocess"

    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds

    def policy(self) -> dict[str, Any]:
        return {
            "backend": self.name,
            "fresh_process_per_candidate_origin": True,
            "timeout_seconds": self.timeout_seconds,
            "network": "not blocked; use Modal for a security boundary",
            "secrets": "minimal environment only",
        }

    def execute(self, request: dict[str, Any]) -> ExecutionResult:
        payload = canonical_json(request)
        request_sha = hashlib.sha256(payload.encode()).hexdigest()
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONHASHSEED": "0",
        }
        started = time.monotonic()
        completed = subprocess.run(
            [sys.executable, "-I", "-m", "rsi_sandbox.worker"],
            input=payload,
            text=True,
            capture_output=True,
            timeout=self.timeout_seconds,
            env=env,
            check=False,
        )
        duration = time.monotonic() - started
        if completed.returncode != 0:
            raise RuntimeError(
                f"worker exited {completed.returncode}: {completed.stderr.strip()[:1000]}"
            )
        return ExecutionResult(
            rows=_parse_output(completed.stdout),
            duration_seconds=duration,
            backend=self.name,
            request_sha256=request_sha,
            stderr=completed.stderr[:1000],
        )


class ModalExecutor:
    name = "modal-sandbox"

    def __init__(
        self,
        app_name: str = "recursive-sandbox-improvement",
        timeout_seconds: int = 60,
    ) -> None:
        self.app_name = app_name
        self.timeout_seconds = timeout_seconds
        try:
            import modal
        except ImportError as exc:
            raise RuntimeError("install the Modal extra: uv sync --extra modal") from exc
        self.modal = modal
        self.app = modal.App.lookup(app_name, create_if_missing=True)
        self.image = modal.Image.debian_slim(python_version="3.12").add_local_python_source(
            "rsi_sandbox", copy=True
        )

    def policy(self) -> dict[str, Any]:
        return {
            "backend": self.name,
            "app": self.app_name,
            "fresh_sandbox_per_candidate_origin": True,
            "runtime": "gvisor",
            "block_network": True,
            "secrets": [],
            "volumes": [],
            "cpu_request_limit": [0.25, 1.0],
            "memory_request_limit_mb": [256, 512],
            "timeout_seconds": self.timeout_seconds,
            "idle_timeout_seconds": 30,
        }

    def execute(self, request: dict[str, Any]) -> ExecutionResult:
        payload = canonical_json(request)
        request_sha = hashlib.sha256(payload.encode()).hexdigest()
        encoded_request = base64.urlsafe_b64encode(
            zlib.compress(payload.encode(), level=9)
        ).decode()
        started = time.monotonic()
        sandbox = self.modal.Sandbox.create(
            "python",
            "-m",
            "rsi_sandbox.worker",
            "--request-zlib-b64",
            encoded_request,
            app=self.app,
            image=self.image,
            env={"PYTHONHASHSEED": "0", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
            secrets=[],
            volumes={},
            timeout=self.timeout_seconds,
            idle_timeout=30,
            cpu=(0.25, 1.0),
            memory=(256, 512),
            runtime="gvisor",
            block_network=True,
        )
        try:
            output = sandbox.stdout.read()
            stderr = sandbox.stderr.read()
            sandbox.wait()
        finally:
            sandbox.terminate(wait=True)
        duration = time.monotonic() - started
        if not output.strip():
            raise RuntimeError(f"Modal worker returned no output: {stderr.strip()[:1000]}")
        return ExecutionResult(
            rows=_parse_output(output),
            duration_seconds=duration,
            backend=self.name,
            request_sha256=request_sha,
            stderr=stderr[:1000],
        )
