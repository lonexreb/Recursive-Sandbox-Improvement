from __future__ import annotations

import math
from collections.abc import Iterable

from .data import Dataset, day_of
from .models import ForecastRow, Metrics

QUANTILES = ((0.1, "q10"), (0.5, "q50"), (0.9, "q90"))


def pinball(y: float, prediction: float, quantile: float) -> float:
    error = y - prediction
    return quantile * error if error >= 0 else (quantile - 1.0) * error


def evaluate_forecasts(
    dataset: Dataset,
    forecasts_by_origin: Iterable[tuple[str, list[ForecastRow]]],
    horizons: tuple[int, ...],
) -> Metrics:
    violations: list[str] = []
    losses: list[float] = []
    baseline_losses: list[float] = []
    covered: list[bool] = []
    absolute_errors: list[float] = []

    for origin, rows in forecasts_by_origin:
        origin_day = day_of(origin)
        row_map: dict[tuple[str, int], ForecastRow] = {}
        for row in rows:
            key = (row.series_id, row.horizon_days)
            if key in row_map:
                violations.append(f"duplicate forecast at {origin}: {key}")
                continue
            row_map[key] = row
            if row.origin_date != origin:
                violations.append(f"origin mismatch at {origin}: {row.origin_date}")
            if row.horizon_days not in horizons:
                violations.append(f"unexpected horizon at {origin}: {row.horizon_days}")
            quantiles = (row.q10, row.q50, row.q90)
            if not all(math.isfinite(value) and value > 0 for value in quantiles):
                violations.append(f"non-positive or non-finite quantile at {origin}: {key}")
            if not row.q10 <= row.q50 <= row.q90:
                violations.append(f"non-monotone quantiles at {origin}: {key}")

        for series_id in dataset.series:
            baseline = dataset.last_value(series_id, origin_day)
            if baseline is None:
                continue
            for horizon in horizons:
                truth = dataset.value_at(series_id, origin_day + horizon)
                if truth is None:
                    continue
                key = (series_id, horizon)
                row = row_map.get(key)
                if row is None:
                    violations.append(f"missing forecast at {origin}: {key}")
                    continue
                cell_losses = [
                    pinball(truth, getattr(row, field), quantile) for quantile, field in QUANTILES
                ]
                cell_baseline = [pinball(truth, baseline, quantile) for quantile, _ in QUANTILES]
                losses.append(sum(cell_losses) / len(cell_losses))
                baseline_losses.append(sum(cell_baseline) / len(cell_baseline))
                covered.append(row.q10 <= truth <= row.q90)
                absolute_errors.append(abs(truth - row.q50))

    if not losses:
        violations.append("no truth-aligned forecast cells")
        return Metrics(0, math.inf, math.inf, -math.inf, 0.0, math.inf, False, tuple(violations))
    mean_loss = sum(losses) / len(losses)
    mean_baseline = sum(baseline_losses) / len(baseline_losses)
    skill = 0.0 if mean_baseline == 0 else 1.0 - mean_loss / mean_baseline
    return Metrics(
        n_cells=len(losses),
        pinball=mean_loss,
        baseline_pinball=mean_baseline,
        skill=skill,
        coverage_80=sum(covered) / len(covered),
        mae_q50=sum(absolute_errors) / len(absolute_errors),
        valid=not violations,
        violations=tuple(violations[:100]),
    )
