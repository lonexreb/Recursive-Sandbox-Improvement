import json

from rsi_sandbox.benchmark import run_benchmark
from rsi_sandbox.synthetic import synthetic_dataset


def test_benchmark_writes_comparable_hashed_report(tmp_path) -> None:
    report = run_benchmark(
        synthetic_dataset("planted", 4, n_series=3, days=260),
        ["2026-05-01", "2026-05-08"],
        (1, 3, 7),
        tmp_path / "report.json",
    )
    saved = json.loads((tmp_path / "report.json").read_text())
    assert saved == report
    assert report["champion_metrics"]["n_cells"] == report["official_drift_metrics"]["n_cells"]
    assert len(report["contract_sha256"]) == len(report["report_sha256"]) == 64
    assert report["status"] == "development_backtest"
