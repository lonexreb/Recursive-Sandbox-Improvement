from rsi_sandbox.executors import LocalExecutor
from rsi_sandbox.models import CandidateConfig


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
