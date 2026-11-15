from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CandidateConfig:
    """The complete, typed mutation surface available to the proposer."""

    name: str
    parent_id: str | None = None
    lookback_days: int = 0
    min_samples: int = 8
    recency_half_life_days: int = 0
    drift_scale: float = 0.0
    interval_scale: float = 0.0

    def __post_init__(self) -> None:
        if not self.name or len(self.name) > 80:
            raise ValueError("candidate name must contain 1-80 characters")
        if self.lookback_days not in {0, 30, 45, 60, 90, 120, 180}:
            raise ValueError("lookback_days is outside the candidate grammar")
        if self.min_samples not in {5, 8, 12, 20}:
            raise ValueError("min_samples is outside the candidate grammar")
        if self.recency_half_life_days not in {0, 14, 30, 45, 60, 90}:
            raise ValueError("recency_half_life_days is outside the candidate grammar")
        if self.drift_scale not in {0.0, 0.25, 0.5, 0.75, 1.0}:
            raise ValueError("drift_scale is outside the candidate grammar")
        if self.interval_scale not in {0.0, 0.75, 1.0, 1.25, 1.5}:
            raise ValueError("interval_scale is outside the candidate grammar")

    @property
    def candidate_id(self) -> str:
        payload = {k: v for k, v in asdict(self).items() if k not in {"name", "parent_id"}}
        digest = hashlib.sha256(canonical_json(payload).encode()).hexdigest()[:12]
        return f"{self.name}-{digest}"

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["candidate_id"] = self.candidate_id
        return out

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> CandidateConfig:
        allowed = {field for field in cls.__dataclass_fields__}
        return cls(**{key: value[key] for key in allowed if key in value})


@dataclass(frozen=True)
class ForecastRow:
    series_id: str
    origin_date: str
    horizon_days: int
    q10: float
    q50: float
    q90: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ForecastRow:
        expected = {"series_id", "origin_date", "horizon_days", "q10", "q50", "q90"}
        if set(value) != expected:
            raise ValueError(f"forecast schema mismatch: expected {sorted(expected)}")
        return cls(
            series_id=str(value["series_id"]),
            origin_date=str(value["origin_date"]),
            horizon_days=int(value["horizon_days"]),
            q10=float(value["q10"]),
            q50=float(value["q50"]),
            q90=float(value["q90"]),
        )


@dataclass(frozen=True)
class Metrics:
    n_cells: int
    pinball: float
    baseline_pinball: float
    skill: float
    coverage_80: float
    mae_q50: float
    valid: bool
    violations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
