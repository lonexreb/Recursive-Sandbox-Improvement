from __future__ import annotations

import hashlib
import json
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
