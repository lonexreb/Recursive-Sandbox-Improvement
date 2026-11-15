import hashlib
import json
import sys
from types import SimpleNamespace

import pytest

from rsi_sandbox.executors import (
    ExecutionError,
    FailureKind,
    LocalExecutor,
    ModalExecutor,
)
from rsi_sandbox.models import CandidateConfig

REQUEST = {
    "schema_version": 1,
    "origin_date": "2026-01-02",
    "horizons": [1],
    "candidate": CandidateConfig(name="flat").to_dict(),
    "series": {"gpu": [["2026-01-01", 1.0], ["2026-01-02", 1.1]]},
}
VALID = '{"schema_version":1,"forecasts":[{"series_id":"gpu","origin_date":"2026-01-02",'
VALID += '"horizon_days":1,"q10":1.0,"q50":1.1,"q90":1.2}]}'


def _local(code: str, **kwargs) -> LocalExecutor:
    return LocalExecutor(command=[sys.executable, "-c", code], **kwargs)


def _kind(executor, request=REQUEST) -> FailureKind:
    with pytest.raises(ExecutionError) as caught:
        executor.execute(request)
    return caught.value.kind


def test_local_success_records_response_hash() -> None:
    result = LocalExecutor(timeout_seconds=10).execute(REQUEST)
    assert len(result.response_sha256) == 64
    assert len(result.request_sha256) == 64


def test_local_valid_json_with_nonzero_exit_is_rejected() -> None:
    code = f"import sys; sys.stdout.write({VALID!r}); sys.exit(3)"
    assert _kind(_local(code)) is FailureKind.NONZERO_EXIT


def test_local_timeout_is_typed() -> None:
    assert _kind(_local("import time; time.sleep(30)", timeout_seconds=1)) is FailureKind.TIMEOUT


def test_local_unbounded_output_is_capped_and_killed() -> None:
    code = "import sys\nwhile True: sys.stdout.write('x' * 65536)"
    executor = _local(code, timeout_seconds=20, max_output_bytes=200_000)
    assert _kind(executor) is FailureKind.OUTPUT_TOO_LARGE


@pytest.mark.parametrize("output", ["not json", "{}", '{"schema_version":1,"forecasts":[{}]}'])
def test_local_malformed_output_is_candidate_failure(output) -> None:
    assert _kind(_local(f"print({output!r})")) is FailureKind.CANDIDATE_FAILURE


def test_local_spawn_failure_is_infrastructure() -> None:
    executor = LocalExecutor(command=["/nonexistent/rsi-worker"])
    assert _kind(executor) is FailureKind.INFRASTRUCTURE_FAILURE


def test_local_stderr_is_not_in_the_typed_message() -> None:
    code = "import sys; sys.stderr.write('/secret/host/path'); sys.exit(2)"
    with pytest.raises(ExecutionError) as caught:
        _local(code).execute(REQUEST)
    assert "/secret/host/path" not in str(caught.value)


# --- Modal: fake SDK, no live call -------------------------------------------------------


class SandboxTimeoutError(Exception):
    pass


class FakeSandbox:
    def __init__(self, out=(VALID,), err=("",), returncode=0, wait_error=None) -> None:
        self.stdout, self.stderr = list(out), list(err)
        self.returncode, self.wait_error = returncode, wait_error
        self.terminated = False

    def wait(self) -> None:
        if self.wait_error:
            raise self.wait_error

    def terminate(self, wait: bool = False) -> None:
        self.terminated = wait


def _fake_modal(monkeypatch, sandbox=None, create_error=None):
    calls = SimpleNamespace(create=[], image=[], lookup=[])

    class Image:
        @staticmethod
        def debian_slim(**kwargs):
            calls.image.append(("debian_slim", kwargs))
            return SimpleNamespace(
                add_local_python_source=lambda *a, **k: calls.image.append(("add", a, k)) or "img"
            )

    class Sandbox:
        @staticmethod
        def create(*args, **kwargs):
            calls.create.append((args, kwargs))
            if create_error:
                raise create_error
            return sandbox

    class App:
        @staticmethod
        def lookup(name, create_if_missing):
            calls.lookup.append((name, create_if_missing))
            return "app"

    monkeypatch.setitem(
        sys.modules, "modal", SimpleNamespace(App=App, Image=Image, Sandbox=Sandbox)
    )
    return calls


def test_modal_creation_arguments_are_pinned(monkeypatch) -> None:
    sandbox = FakeSandbox()
    calls = _fake_modal(monkeypatch, sandbox)
    executor = ModalExecutor()
    result = executor.execute(REQUEST)

    (args, kwargs) = calls.create[0]
    assert args[:4] == ("python", "-m", "rsi_sandbox.worker", "--request-zlib-b64")
    assert kwargs == {
        "app": "app",
        "image": "img",
        "env": {"PYTHONHASHSEED": "0", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        "secrets": [],
        "volumes": {},
        "timeout": 60,
        "idle_timeout": 30,
        "cpu": (0.25, 1.0),
        "memory": (256, 512),
        "runtime": "gvisor",
        "block_network": True,
    }
    assert ("debian_slim", {"python_version": "3.12"}) in calls.image
    assert ("add", ("rsi_sandbox",), {"copy": True}) in calls.image
    assert calls.lookup == [("recursive-sandbox-improvement", True)]
    assert sandbox.terminated
    assert result.response_sha256 == hashlib.sha256(VALID.encode()).hexdigest()
    assert json.loads(json.dumps(executor.policy()))["block_network"] is True


@pytest.mark.parametrize(
    ("sandbox", "kind"),
    [
        (FakeSandbox(returncode=2), FailureKind.NONZERO_EXIT),  # valid JSON, failed exit
        (FakeSandbox(returncode=124), FailureKind.TIMEOUT),
        (FakeSandbox(wait_error=SandboxTimeoutError()), FailureKind.TIMEOUT),
        (FakeSandbox(wait_error=RuntimeError("boom")), FailureKind.INFRASTRUCTURE_FAILURE),
        (FakeSandbox(returncode=None), FailureKind.INFRASTRUCTURE_FAILURE),
        (FakeSandbox(returncode=137), FailureKind.INFRASTRUCTURE_FAILURE),
        (FakeSandbox(out=("not json",)), FailureKind.CANDIDATE_FAILURE),
        (FakeSandbox(out=("x" * 100_000,) * 60), FailureKind.OUTPUT_TOO_LARGE),
    ],
)
def test_modal_failure_taxonomy(monkeypatch, sandbox, kind) -> None:
    _fake_modal(monkeypatch, sandbox)
    assert _kind(ModalExecutor()) is kind
    assert sandbox.terminated  # always cleaned up


def test_modal_create_failure_is_infrastructure(monkeypatch) -> None:
    _fake_modal(monkeypatch, create_error=RuntimeError("quota"))
    assert _kind(ModalExecutor()) is FailureKind.INFRASTRUCTURE_FAILURE


def test_modal_stdout_overflow_terminates_without_waiting_for_stderr(monkeypatch) -> None:
    class BlockingStderr:
        def __iter__(self):
            raise AssertionError("stderr must not be read after stdout exceeds its cap")

    sandbox = FakeSandbox(out=("x" * 100_000,) * 60)
    sandbox.stderr = BlockingStderr()
    _fake_modal(monkeypatch, sandbox)
    assert _kind(ModalExecutor()) is FailureKind.OUTPUT_TOO_LARGE
    assert sandbox.terminated


def test_installed_modal_sdk_reports_exit_status() -> None:
    modal = pytest.importorskip("modal")
    assert isinstance(modal.Sandbox.returncode, property)
    assert callable(modal.Sandbox.wait)
