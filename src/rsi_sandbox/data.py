from __future__ import annotations

import csv
import hashlib
import re
import statistics
from collections import defaultdict
from contextlib import suppress
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


def day_of(value: str) -> int:
    return date.fromisoformat(value).toordinal()


def iso(day: int) -> str:
    return date.fromordinal(day).isoformat()


def slug(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9]+", "_", value)).strip("_")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class Point:
    day: int
    value: float


@dataclass
class Dataset:
    series: dict[str, list[Point]]
    source_path: Path
    source_sha256: str
    cutoff: str
    scope: str

    def history_request(
        self,
        origin: str,
        horizons: tuple[int, ...],
        candidate: dict[str, Any],
    ) -> dict[str, Any]:
        origin_day = day_of(origin)
        histories: dict[str, list[list[str | float]]] = {}
        for series_id, points in self.series.items():
            visible = [[iso(point.day), point.value] for point in points if point.day <= origin_day]
            if visible:
                histories[series_id] = visible
        return {
            "schema_version": 1,
            "origin_date": origin,
            "horizons": list(horizons),
            "candidate": candidate,
            "series": histories,
        }

    def value_at(self, series_id: str, target_day: int) -> float | None:
        for point in self.series.get(series_id, []):
            if point.day == target_day:
                return point.value
            if point.day > target_day:
                break
        return None

    def last_value(self, series_id: str, origin_day: int) -> float | None:
        value = None
        for point in self.series.get(series_id, []):
            if point.day > origin_day:
                break
            value = point.value
        return value

    def manifest(self) -> dict[str, Any]:
        return {
            "source": self.source_path.name,
            "sha256": self.source_sha256,
            "cutoff": self.cutoff,
            "scope": self.scope,
            "series": len(self.series),
            "points": sum(len(points) for points in self.series.values()),
        }


def load_pack(pack: str | Path, cutoff: str = "2026-11-06") -> Dataset:
    """Load daily-statistics series using the official pack's headline gates."""

    source = Path(pack).expanduser().resolve() / "daily_statistics.csv"
    if not source.is_file():
        raise FileNotFoundError(f"missing {source}")
    cutoff_day = day_of(cutoff)
    points_by_series: dict[str, dict[int, Point]] = defaultdict(dict)
    providers_by_series: dict[str, list[float]] = defaultdict(list)

    with source.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["date"] > cutoff or row["source_id"] == "ewyluda":
                continue
            try:
                value = float(row["median_usd_per_gpu_hour"])
            except (TypeError, ValueError):
                continue
            if value <= 0:
                continue
            series_id = ".".join(
                (
                    row["source_id"],
                    row["instrument_class"],
                    slug(row["gpu_model"]),
                    row["pricing_tier"],
                    "median",
                )
            )
            point = Point(day=day_of(row["date"]), value=value)
            points_by_series[series_id][point.day] = point
            with suppress(TypeError, ValueError):
                providers_by_series[series_id].append(float(row["n_providers"]))

    selected: dict[str, list[Point]] = {}
    for series_id, by_day in points_by_series.items():
        points = sorted(by_day.values(), key=lambda point: point.day)
        if len(points) < 60:
            continue
        if cutoff_day - points[-1].day > 3:
            continue
        distinct_90 = len(
            {round(point.value, 6) for point in points if point.day > cutoff_day - 90}
        )
        if distinct_90 < 5:
            continue
        providers = providers_by_series[series_id]
        if not providers or statistics.median(providers) < 3:
            continue
        selected[series_id] = points

    if not selected:
        raise ValueError("headline gates selected no series")
    return Dataset(
        series=dict(sorted(selected.items())),
        source_path=source,
        source_sha256=sha256_file(source),
        cutoff=cutoff,
        scope="official daily_statistics headline gates",
    )


def load_series_file(
    series_file: str | Path,
    catalog_file: str | Path,
    cutoff: str = "2026-11-06",
    tier: str = "headline",
) -> Dataset:
    """Load starter-generated series and catalog files, including future truth rows."""

    source = Path(series_file).expanduser().resolve()
    catalog = Path(catalog_file).expanduser().resolve()
    with catalog.open(newline="", encoding="utf-8") as handle:
        selected_ids = {
            row["series_id"]
            for row in csv.DictReader(handle)
            if tier == "all" or row["tier"] == tier
        }
    series: dict[str, list[Point]] = defaultdict(list)
    with source.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["series_id"] not in selected_ids:
                continue
            try:
                value = float(row["value"])
            except (TypeError, ValueError):
                continue
            if value > 0:
                series[row["series_id"]].append(Point(day=day_of(row["date"]), value=value))
    for points in series.values():
        points.sort(key=lambda point: point.day)
    return Dataset(
        series=dict(sorted(series.items())),
        source_path=source,
        source_sha256=sha256_file(source),
        cutoff=cutoff,
        scope=f"starter catalog tier={tier}; catalog_sha256={sha256_file(catalog)}",
    )
