from __future__ import annotations

import math
from datetime import date
from typing import Any

from .models import CandidateConfig, ForecastRow


def _ordinal(value: str) -> int:
    return date.fromisoformat(value).toordinal()


def weighted_quantile(values: list[float], weights: list[float], quantile: float) -> float:
    ordered = sorted(zip(values, weights, strict=True), key=lambda item: item[0])
    total = sum(weight for _, weight in ordered)
    threshold = quantile * total
    cumulative = 0.0
    for value, weight in ordered:
        cumulative += weight
        if cumulative >= threshold:
            return value
    return ordered[-1][0]


def _changes(
    points: list[tuple[int, float]], horizon: int, origin_day: int, half_life: int
) -> tuple[list[float], list[float]]:
    by_day = dict(points)
    values: list[float] = []
    weights: list[float] = []
    for current_day, current_value in points:
        prior = by_day.get(current_day - horizon)
        if prior is None or prior <= 0 or current_value <= 0:
            continue
        values.append(math.log(current_value / prior))
        if half_life:
            age = max(0, origin_day - current_day)
            weights.append(math.exp(math.log(0.5) * age / half_life))
        else:
            weights.append(1.0)
    return values, weights


def forecast_request(request: dict[str, Any]) -> list[ForecastRow]:
    if request.get("schema_version") != 1:
        raise ValueError("unsupported request schema")
    candidate = CandidateConfig.from_dict(request["candidate"])
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
        if candidate.lookback_days:
            points = [
                (day, value) for day, value in points if day > origin_day - candidate.lookback_days
            ]
        if not points:
            continue
        last = points[-1][1]
        for horizon in horizons:
            changes, weights = _changes(
                points,
                horizon,
                origin_day,
                candidate.recency_half_life_days,
            )
            if len(changes) < candidate.min_samples:
                q10 = q50 = q90 = last
            else:
                raw_q10 = weighted_quantile(changes, weights, 0.1)
                raw_q50 = weighted_quantile(changes, weights, 0.5)
                raw_q90 = weighted_quantile(changes, weights, 0.9)
                center = candidate.drift_scale * raw_q50
                lower = center + candidate.interval_scale * (raw_q10 - raw_q50)
                upper = center + candidate.interval_scale * (raw_q90 - raw_q50)
                q10 = last * math.exp(lower)
                q50 = last * math.exp(center)
                q90 = last * math.exp(upper)
            q10, q50, q90 = sorted((max(q10, 1e-9), max(q50, 1e-9), max(q90, 1e-9)))
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
