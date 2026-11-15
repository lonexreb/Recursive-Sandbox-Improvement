import base64
import json
import zlib

from rsi_sandbox.executors import LocalExecutor
from rsi_sandbox.models import CandidateConfig, canonical_json
from rsi_sandbox.worker import main as worker_main


def test_local_executor_uses_typed_worker_contract() -> None:
    request = {
        "schema_version": 1,
        "origin_date": "2026-01-02",
        "horizons": [1],
        "candidate": CandidateConfig(name="flat").to_dict(),
        "series": {"gpu": [["2026-01-01", 1.0], ["2026-01-02", 1.1]]},
    }

    result = LocalExecutor(timeout_seconds=10).execute(request)

    assert result.backend == "local-subprocess"
    assert len(result.rows) == 1
    assert result.rows[0].q50 == 1.1


def test_worker_accepts_compressed_noninteractive_request(capsys) -> None:
    request = {
        "schema_version": 1,
        "origin_date": "2026-01-02",
        "horizons": [1],
        "candidate": CandidateConfig(name="flat").to_dict(),
        "series": {"gpu": [["2026-01-02", 1.1]]},
    }
    encoded = base64.urlsafe_b64encode(zlib.compress(canonical_json(request).encode())).decode()

    result = worker_main(["--request-zlib-b64", encoded])
    response = json.loads(capsys.readouterr().out)

    assert result == 0
    assert response["schema_version"] == 1
    assert response["forecasts"][0]["q50"] == 1.1
