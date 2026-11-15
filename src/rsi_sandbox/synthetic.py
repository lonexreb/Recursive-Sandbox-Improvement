from __future__ import annotations

import hashlib
import math
import random
from pathlib import Path

from .data import Dataset, Point, day_of, iso
from .models import canonical_json

START = "2026-01-01"
FIRST_ORIGIN = "2026-05-01"  # 120 days of history before the first study origin


def _series(kind: str, seed: int, index: int, days: int) -> list[float]:
    """Causal generator: day t depends only on days < t plus fresh randomness."""

    rng = random.Random(f"{kind}:{seed}:{index}")
    level = math.log(rng.uniform(1.0, 4.0))
    values = []
    for _ in range(days):
        if kind == "planted":  # steady trend under noise: drift and interval both pay
            values.append(math.exp(level := level + 0.006 + 0.02 * rng.gauss(0, 1)))
        else:  # null: constant level, rare unpredictable one-day shocks
            shock = rng.choice((-1, 1)) * rng.uniform(0.05, 0.2) if rng.random() < 0.12 else 0.0
            values.append(math.exp(level + shock))
    return values


def synthetic_dataset(kind: str, seed: int = 0, n_series: int = 6, days: int = 560) -> Dataset:
    if kind not in ("planted", "null"):
        raise ValueError("kind must be 'planted' or 'null'")
    start = day_of(START)
    series = {
        f"synthetic.{kind}.{i}": [
            Point(start + offset, value)
            for offset, value in enumerate(_series(kind, seed, i, days))
        ]
        for i in range(n_series)
    }
    body = {sid: [[p.day, p.value] for p in points] for sid, points in series.items()}
    return Dataset(
        series=series,
        source_path=Path(f"synthetic-{kind}-{seed}"),
        source_sha256=hashlib.sha256(canonical_json(body).encode()).hexdigest(),
        cutoff=iso(start + days - 1),
        scope=f"synthetic {kind} seed={seed}",
    )
