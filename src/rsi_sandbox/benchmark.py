from __future__ import annotations

import hashlib
import itertools
import json
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import evaluation
from .baselines import official_drift_request
from .data import Dataset, sha256_file
from .evaluation import evaluate_forecasts
from .forecast import forecast_request
from .loop import _json_safe, provenance
from .models import CandidateConfig, canonical_json

SHOWCASE_CHAMPION = CandidateConfig(
    name="showcase-champion",
    lookback_days=45,
    min_samples=5,
    recency_half_life_days=14,
    drift_scale=0.25,
    interval_scale=1.25,
)


def paired_origin_inference(records: list[dict[str, Any]], samples: int = 20_000) -> dict[str, Any]:
    """Deterministic paired sign-flip test and origin-block bootstrap interval."""

    if not records or len(records) > 20:
        raise ValueError("paired origin inference supports 1-20 origin blocks")
    differences = [record["champion_pinball"] - record["drift_pinball"] for record in records]
    observed = abs(sum(differences)) - 1e-15
    hits = sum(
        abs(sum(sign * value for sign, value in zip(signs, differences, strict=True))) >= observed
        for signs in itertools.product((-1, 1), repeat=len(differences))
    )
    rng = random.Random(20_261_115)
    bootstrapped = []
    for _ in range(samples):
        chosen = [records[rng.randrange(len(records))] for _ in records]
        cells = sum(record["cells"] for record in chosen)
        difference = sum(
            (record["champion_pinball"] - record["drift_pinball"]) * record["cells"]
            for record in chosen
        )
        bootstrapped.append(difference / cells)
    bootstrapped.sort()
    interval = [
        bootstrapped[int(0.05 * samples)],
        bootstrapped[int(0.95 * samples) - 1],
    ]
    conclusive = interval[1] < 0 or interval[0] > 0
    return {
        "unit": "weekly origin block",
        "champion_wins": sum(value < 0 for value in differences),
        "blocks": len(records),
        "mean_origin_pinball_delta": sum(differences) / len(differences),
        "exact_two_sided_sign_flip_p": hits / (2 ** len(differences)),
        "weighted_pinball_delta_bootstrap_90_ci": interval,
        "bootstrap_samples": samples,
        "interpretation": (
            "Negative favors the champion. "
            + (
                "The interval excludes zero."
                if conclusive
                else (
                    "The interval includes zero, so this public development result is "
                    "promising but not statistically conclusive."
                )
            )
        ),
    }


def run_benchmark(
    dataset: Dataset,
    origins: list[str],
    horizons: tuple[int, ...],
    output_path: Path,
    champion: CandidateConfig = SHOWCASE_CHAMPION,
) -> dict[str, Any]:
    """Score the frozen champion and official drift baseline on identical cells."""

    if not origins:
        raise ValueError("benchmark needs at least one origin")
    champion_forecasts = []
    drift_forecasts = []
    for origin in origins:
        request = dataset.history_request(origin, horizons, champion.to_dict())
        champion_forecasts.append((origin, forecast_request(request)))
        drift_forecasts.append((origin, official_drift_request(request)))

    champion_metrics = evaluate_forecasts(dataset, champion_forecasts, horizons)
    drift_metrics = evaluate_forecasts(dataset, drift_forecasts, horizons)
    if not champion_metrics.valid or not drift_metrics.valid:
        raise ValueError("benchmark generated invalid forecasts")
    if champion_metrics.n_cells != drift_metrics.n_cells:
        raise ValueError("benchmark methods changed the scored cell set")

    origin_records = []
    for (origin, champion_rows), (_, drift_rows) in zip(
        champion_forecasts, drift_forecasts, strict=True
    ):
        champion_origin = evaluate_forecasts(dataset, [(origin, champion_rows)], horizons)
        drift_origin = evaluate_forecasts(dataset, [(origin, drift_rows)], horizons)
        if champion_origin.n_cells != drift_origin.n_cells:
            raise ValueError(f"methods changed the scored cell set at {origin}")
        origin_records.append(
            {
                "origin": origin,
                "cells": champion_origin.n_cells,
                "champion_pinball": champion_origin.pinball,
                "drift_pinball": drift_origin.pinball,
                "champion_skill": champion_origin.skill,
                "drift_skill": drift_origin.skill,
                "champion_coverage_80": champion_origin.coverage_80,
                "drift_coverage_80": drift_origin.coverage_80,
            }
        )

    contract = {
        "origins": origins,
        "horizons": list(horizons),
        "champion": champion.to_dict(),
        "comparison": "official starter empirical drift, min_samples=20",
    }
    report: dict[str, Any] = _json_safe(
        {
            "schema_version": 1,
            "status": "development_backtest",
            "created_at_utc": datetime.now(UTC).isoformat(),
            "warning": (
                "Origins are public development evidence, not a fresh or hidden confirmation set."
            ),
            "contract": contract,
            "contract_sha256": hashlib.sha256(canonical_json(contract).encode()).hexdigest(),
            "data": dataset.manifest(),
            "provenance": provenance(),
            "evaluator_sha256": sha256_file(Path(evaluation.__file__)),
            "champion_metrics": champion_metrics.to_dict(),
            "official_drift_metrics": drift_metrics.to_dict(),
            "by_origin": origin_records,
            "paired_inference": paired_origin_inference(origin_records),
            "comparison": {
                "skill_delta": champion_metrics.skill - drift_metrics.skill,
                "pinball_reduction_fraction": 1.0
                - champion_metrics.pinball / drift_metrics.pinball,
            },
        }
    )
    stable = {key: value for key, value in report.items() if key != "created_at_utc"}
    report["report_sha256"] = hashlib.sha256(canonical_json(stable).encode()).hexdigest()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report
