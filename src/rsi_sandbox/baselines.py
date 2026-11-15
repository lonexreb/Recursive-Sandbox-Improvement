from __future__ import annotations

import math
from datetime import date
from typing import Any

from .models import ForecastRow


def _ordinal(value: str) -> int:
    return date.fromisoformat(value).toordinal()


def linear_quantile(values: list[float], quantile: float) -> float:
    """NumPy-compatible linear quantile for a non-empty finite sample."""

    if not values:
        raise ValueError("quantile needs at least one value")
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("quantile must be between zero and one")
    ordered = sorted(values)
    index = quantile * (len(ordered) - 1)
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    weight = index - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def official_drift_request(request: dict[str, Any], min_samples: int = 20) -> list[ForecastRow]:
    """Reproduce the event starter's empirical-drift baseline without NumPy.

    This is trusted comparison code, never candidate code. It consumes the same truncated
    history request as a sandbox candidate and is scored by the same evaluator.
    """

    if request.get("schema_version") != 1:
        raise ValueError("unsupported request schema")
    origin = str(request["origin_date"])
    origin_day = _ordinal(origin)
    horizons = tuple(int(value) for value in request["horizons"])
    if not horizons or any(value not in {1, 3, 7} for value in horizons):
        raise ValueError("horizons must be a non-empty subset of 1, 3, 7")

    output: list[ForecastRow] = []
    for series_id, raw_points in sorted(request["series"].items()):
        points = [(_ordinal(str(day)), float(value)) for day, value in raw_points]
        if any(day > origin_day for day, _ in points):
            raise ValueError("history contains a point after the forecast origin")
        if not points:
            continue
        by_day = dict(points)
        last = points[-1][1]
        for horizon in horizons:
            changes = [
                math.log(value / by_day[day - horizon])
                for day, value in points
                if day - horizon in by_day and value > 0 and by_day[day - horizon] > 0
            ]
            if len(changes) < min_samples:
                q10 = q50 = q90 = last
            else:
                q10, q50, q90 = (
                    last * math.exp(linear_quantile(changes, quantile))
                    for quantile in (0.1, 0.5, 0.9)
                )
            output.append(
                ForecastRow(
                    series_id=series_id,
                    origin_date=origin,
                    horizon_days=horizon,
                    q10=q10,
                    q50=q50,
                    q90=q90,
                )
            )
    return output
