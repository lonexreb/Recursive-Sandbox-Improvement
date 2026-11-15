import json

from rsi_sandbox.benchmark import paired_origin_inference, run_benchmark
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
    assert len(report["by_origin"]) == 2
    assert report["paired_inference"]["blocks"] == 2


def test_paired_inference_is_exact_and_deterministic() -> None:
    records = [
        {"cells": 10, "champion_pinball": 1.0, "drift_pinball": 2.0},
        {"cells": 10, "champion_pinball": 1.0, "drift_pinball": 2.0},
    ]
    first = paired_origin_inference(records, samples=100)
    assert first == paired_origin_inference(records, samples=100)
    assert first["champion_wins"] == 2
    assert first["exact_two_sided_sign_flip_p"] == 0.5
    assert first["weighted_pinball_delta_bootstrap_90_ci"] == [-1.0, -1.0]
