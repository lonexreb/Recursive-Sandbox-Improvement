from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import zlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from .models import ForecastRow, canonical_json

MAX_OUTPUT_BYTES = 5_000_000
MAX_STDERR_BYTES = 65_536


class FailureKind(StrEnum):
    TIMEOUT = "timeout"
    NONZERO_EXIT = "nonzero_exit"
    OUTPUT_TOO_LARGE = "output_too_large"
    CANDIDATE_FAILURE = "candidate_failure"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"


class ExecutionError(RuntimeError):
    """Typed executor failure; raw stderr is deliberately never attached."""

    def __init__(self, kind: FailureKind, detail: str = "") -> None:
        super().__init__(f"{kind.value}: {detail}" if detail else kind.value)
        self.kind = kind


@dataclass(frozen=True)
class ExecutionResult:
    rows: list[ForecastRow]
    duration_seconds: float
    backend: str
    request_sha256: str
    stderr: str = ""
    response_sha256: str = ""


class Executor(Protocol):
    name: str

    def execute(self, request: dict[str, Any]) -> ExecutionResult: ...

    def policy(self) -> dict[str, Any]: ...


def _parse_output(raw: bytes) -> list[ForecastRow]:
    if len(raw) > MAX_OUTPUT_BYTES:
        raise ExecutionError(FailureKind.OUTPUT_TOO_LARGE, "worker output exceeded 5 MB")
    try:
        value = json.loads(raw)
        if set(value) != {"schema_version", "forecasts"} or value["schema_version"] != 1:
            raise ValueError("worker response schema mismatch")
        return [ForecastRow.from_dict(row) for row in value["forecasts"]]
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise ExecutionError(FailureKind.CANDIDATE_FAILURE, type(exc).__name__) from None


def _finish(backend: str, payload: str, started: float, out: bytes, err: str) -> ExecutionResult:
    return ExecutionResult(
        rows=_parse_output(out),
        duration_seconds=time.monotonic() - started,
        backend=backend,
        request_sha256=hashlib.sha256(payload.encode()).hexdigest(),
        stderr=err[:1000],
        response_sha256=hashlib.sha256(out).hexdigest(),
    )


class LocalExecutor:
    """Fresh subprocess per request. Not a network or filesystem isolation boundary."""

    name = "local-subprocess"

    def __init__(
        self,
        timeout_seconds: int = 30,
        max_output_bytes: int = MAX_OUTPUT_BYTES,
        command: list[str] | None = None,  # test hook; production always runs the worker
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes
        self.command = command or [sys.executable, "-I", "-m", "rsi_sandbox.worker"]

    def policy(self) -> dict[str, Any]:
        return {
            "backend": self.name,
            "fresh_process_per_candidate_origin": True,
            "timeout_seconds": self.timeout_seconds,
            "cpu_limit_seconds": self.timeout_seconds,
            "max_output_bytes": self.max_output_bytes,
            "network": "not blocked; use Modal for a security boundary",
            "secrets": "minimal environment only",
        }

    def execute(self, request: dict[str, Any]) -> ExecutionResult:
        payload = canonical_json(request)
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONHASHSEED": "0",
        }
        cap, cpu = self.max_output_bytes, self.timeout_seconds

        def limit() -> None:  # runs in the child: caps CPU time and any file it can write
            import resource

            resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
            resource.setrlimit(resource.RLIMIT_FSIZE, (cap + 1, cap + 1))

        started = time.monotonic()
        # stdout/stderr go to size-limited temp files, so the host never buffers more than `cap`
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            try:
                done = subprocess.run(
                    self.command,
                    input=payload.encode(),
                    stdout=out,
                    stderr=err,
                    env=env,
                    timeout=self.timeout_seconds,
                    preexec_fn=limit,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                raise ExecutionError(FailureKind.TIMEOUT, f"> {self.timeout_seconds}s") from None
            except OSError as exc:
                kind = FailureKind.INFRASTRUCTURE_FAILURE
                raise ExecutionError(kind, type(exc).__name__) from None
            if out.seek(0, os.SEEK_END) > cap or err.seek(0, os.SEEK_END) > cap:
                raise ExecutionError(FailureKind.OUTPUT_TOO_LARGE)
            out.seek(0)
            err.seek(0)
            stdout, stderr = out.read(), err.read(MAX_STDERR_BYTES).decode(errors="replace")
        if done.returncode != 0:
            raise ExecutionError(FailureKind.NONZERO_EXIT, f"exit {done.returncode}")
        return _finish(self.name, payload, started, stdout, stderr)


def _read_capped(stream: Any, cap: int) -> tuple[bytes, bool]:
    data = b""
    for chunk in stream:
        data += chunk.encode() if isinstance(chunk, str) else bytes(chunk)
        if len(data) > cap:
            return data[:cap], True
    return data, False


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
        encoded_request = base64.urlsafe_b64encode(
            zlib.compress(payload.encode(), level=9)
        ).decode()
        started = time.monotonic()
        try:
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
        except Exception as exc:
            raise ExecutionError(FailureKind.INFRASTRUCTURE_FAILURE, type(exc).__name__) from None
        try:
            try:
                out, too_big = _read_capped(sandbox.stdout, MAX_OUTPUT_BYTES)
                if too_big:
                    raise ExecutionError(FailureKind.OUTPUT_TOO_LARGE, "stdout exceeded cap")
                err, too_big = _read_capped(sandbox.stderr, MAX_STDERR_BYTES)
                if too_big:
                    raise ExecutionError(FailureKind.OUTPUT_TOO_LARGE, "stderr exceeded cap")
                sandbox.wait()
            except ExecutionError:
                raise
            except Exception as exc:
                timed_out = "Timeout" in type(exc).__name__
                raise ExecutionError(
                    FailureKind.TIMEOUT if timed_out else FailureKind.INFRASTRUCTURE_FAILURE,
                    type(exc).__name__,
                ) from None
            code, stderr = sandbox.returncode, err.decode(errors="replace")
            if code == 124:
                raise ExecutionError(FailureKind.TIMEOUT, "sandbox timeout")
            if code is None or code == 137:
                raise ExecutionError(FailureKind.INFRASTRUCTURE_FAILURE, f"exit {code}")
            if code != 0:
                raise ExecutionError(FailureKind.NONZERO_EXIT, f"exit {code}")
        finally:
            sandbox.terminate(wait=True)
        return _finish(self.name, payload, started, out, stderr)
