from rsi_sandbox.forecast import forecast_request
from rsi_sandbox.models import CandidateConfig


def test_forecaster_emits_positive_monotone_quantiles() -> None:
    request = {
        "schema_version": 1,
        "origin_date": "2026-01-20",
        "horizons": [1, 3, 7],
        "candidate": CandidateConfig(
            name="empirical",
            min_samples=5,
            drift_scale=0.5,
            interval_scale=1.0,
        ).to_dict(),
        "series": {"gpu": [[f"2026-01-{day:02d}", 1.0 + 0.01 * day] for day in range(1, 21)]},
    }

    rows = forecast_request(request)

    assert len(rows) == 3
    assert all(0 < row.q10 <= row.q50 <= row.q90 for row in rows)
    assert {row.horizon_days for row in rows} == {1, 3, 7}


def test_forecaster_refuses_future_history() -> None:
    request = {
        "schema_version": 1,
        "origin_date": "2026-01-01",
        "horizons": [1],
        "candidate": CandidateConfig(name="flat").to_dict(),
        "series": {"gpu": [["2026-01-02", 1.0]]},
    }

    try:
        forecast_request(request)
    except ValueError as exc:
        assert "after the forecast origin" in str(exc)
    else:
        raise AssertionError("future history was accepted")
