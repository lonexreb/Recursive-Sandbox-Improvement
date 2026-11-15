import math

import pytest

from rsi_sandbox.baselines import linear_quantile, official_drift_request


def test_linear_quantile_matches_numpy_default_examples() -> None:
    values = [0.0, 10.0, 20.0, 30.0]
    assert linear_quantile(values, 0.1) == pytest.approx(3.0)
    assert linear_quantile(values, 0.5) == pytest.approx(15.0)
    assert linear_quantile(values, 0.9) == pytest.approx(27.0)


def test_official_drift_uses_only_truncated_history() -> None:
    request = {
        "schema_version": 1,
        "origin_date": "2026-01-10",
        "horizons": [1],
        "candidate": {},
        "series": {"gpu": [[f"2026-01-{day:02d}", math.exp(day / 100)] for day in range(1, 11)]},
    }
    row = official_drift_request(request, min_samples=8)[0]
    assert row.origin_date == "2026-01-10"
    assert row.q10 == pytest.approx(row.q50)
    assert row.q50 == pytest.approx(row.q90)
    assert row.q50 > math.exp(0.10)
