from pathlib import Path

from rsi_sandbox.data import Dataset, Point, day_of
from rsi_sandbox.evaluation import evaluate_forecasts
from rsi_sandbox.loop import promotion_reasons
from rsi_sandbox.models import ForecastRow, Metrics


def _dataset() -> Dataset:
    return Dataset(
        series={
            "gpu": [
                Point(day=day_of("2026-01-01"), value=1.0),
                Point(day=day_of("2026-01-02"), value=1.2),
            ]
        },
        source_path=Path("fixture.csv"),
        source_sha256="fixture",
        cutoff="2026-01-01",
        scope="test",
    )


def test_evaluator_scores_only_after_worker_returns() -> None:
    rows = [ForecastRow("gpu", "2026-01-01", 1, 1.1, 1.2, 1.3)]

    metrics = evaluate_forecasts(_dataset(), [("2026-01-01", rows)], (1,))

    assert metrics.valid
    assert metrics.n_cells == 1
    assert metrics.skill > 0
    assert metrics.coverage_80 == 1.0


def test_gate_rejects_skill_regression() -> None:
    incumbent = Metrics(10, 1.0, 1.0, 0.1, 0.8, 1.0, True)
    candidate = Metrics(10, 1.1, 1.0, -0.1, 0.8, 1.0, True)

    reasons = promotion_reasons(candidate, incumbent, 0.002, 0.05)

    assert any("skill gain" in reason for reason in reasons)
