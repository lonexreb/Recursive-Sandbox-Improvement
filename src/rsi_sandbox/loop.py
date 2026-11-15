from __future__ import annotations

import csv
import json
import math
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .data import Dataset, day_of, iso
from .evaluation import evaluate_forecasts
from .executors import ExecutionResult, Executor
from .models import CandidateConfig, ForecastRow, Metrics
from .proposer import BoundedProposer, signature


def date_origins(start: str, end: str, step_days: int = 7) -> list[str]:
    first, last = day_of(start), day_of(end)
    if first > last or step_days < 1:
        raise ValueError("invalid origin range")
    return [iso(day) for day in range(first, last + 1, step_days)]


def _failure_metrics(message: str) -> Metrics:
    return Metrics(
        n_cells=0,
        pinball=math.inf,
        baseline_pinball=math.inf,
        skill=-math.inf,
        coverage_80=0.0,
        mae_q50=math.inf,
        valid=False,
        violations=(message,),
    )


def evaluate_candidate(
    dataset: Dataset,
    candidate: CandidateConfig,
    origins: list[str],
    horizons: tuple[int, ...],
    executor: Executor,
) -> tuple[Metrics, list[dict[str, Any]], list[tuple[str, list[ForecastRow]]]]:
    traces: list[dict[str, Any]] = []
    forecasts: list[tuple[str, list[ForecastRow]]] = []
    for origin in origins:
        request = dataset.history_request(origin, horizons, candidate.to_dict())
        try:
            result: ExecutionResult = executor.execute(request)
        except Exception as exc:
            traces.append(
                {
                    "event": "experiment_failed",
                    "candidate_id": candidate.candidate_id,
                    "origin": origin,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            return _failure_metrics(traces[-1]["error"]), traces, forecasts
        forecasts.append((origin, result.rows))
        traces.append(
            {
                "event": "experiment_completed",
                "candidate_id": candidate.candidate_id,
                "origin": origin,
                "request_sha256": result.request_sha256,
                "backend": result.backend,
                "duration_seconds": round(result.duration_seconds, 6),
                "forecast_rows": len(result.rows),
            }
        )
    return evaluate_forecasts(dataset, forecasts, horizons), traces, forecasts


def promotion_reasons(
    candidate: Metrics,
    incumbent: Metrics,
    min_skill_gain: float,
    max_coverage_regression: float,
) -> list[str]:
    reasons = []
    if not candidate.valid:
        reasons.append("candidate failed schema or invariant checks")
    if candidate.n_cells != incumbent.n_cells:
        reasons.append("candidate changed the scored cell set")
    if candidate.skill < incumbent.skill + min_skill_gain:
        reasons.append(f"skill gain {candidate.skill - incumbent.skill:.6f} < {min_skill_gain:.6f}")
    if candidate.coverage_80 < incumbent.coverage_80 - max_coverage_regression:
        reasons.append("interval coverage regressed beyond tolerance")
    return reasons


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _write_forecast(path: Path, rows: list[ForecastRow], candidate: CandidateConfig) -> None:
    fields = [
        "series_id",
        "origin_date",
        "horizon_days",
        "q10",
        "q50",
        "q90",
        "target_date",
        "method",
        "method_note",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            value = row.to_dict()
            value["target_date"] = iso(day_of(row.origin_date) + row.horizon_days)
            value["method"] = "recursive_sandbox_improvement"
            value["method_note"] = f"candidate_id={candidate.candidate_id}"
            writer.writerow(value)


def run_improvement(
    dataset: Dataset,
    executor: Executor,
    output_dir: Path,
    train_origins: list[str],
    heldout_origins: list[str],
    cutoff: str,
    horizons: tuple[int, ...] = (1, 3, 7),
    generations: int = 2,
    candidates_per_generation: int = 4,
    seed: int = 7,
    min_skill_gain: float = 0.002,
    max_coverage_regression: float = 0.05,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    proposer = BoundedProposer(seed=seed)
    incumbent = CandidateConfig(name="flat-last-value")
    seen = {signature(incumbent)}
    all_traces: list[dict[str, Any]] = []
    experiments: list[dict[str, Any]] = []
    lineage = [incumbent.candidate_id]

    print(f"data: {len(dataset.series)} series | sha256 {dataset.source_sha256[:12]}")
    print(f"backend: {executor.name} | train origins: {', '.join(train_origins)}")
    incumbent_metrics, traces, _ = evaluate_candidate(
        dataset, incumbent, train_origins, horizons, executor
    )
    all_traces.extend(traces)
    if not incumbent_metrics.valid:
        raise RuntimeError(f"incumbent evaluation failed: {incumbent_metrics.violations[:3]}")
    print(
        f"incumbent {incumbent.candidate_id}: skill={incumbent_metrics.skill:.4f} "
        f"coverage={incumbent_metrics.coverage_80:.3f}"
    )

    for generation in range(1, generations + 1):
        proposals = proposer.propose(
            incumbent,
            generation,
            candidates_per_generation,
            seen,
        )
        eligible: list[tuple[CandidateConfig, Metrics]] = []
        for candidate in proposals:
            seen.add(signature(candidate))
            metrics, traces, _ = evaluate_candidate(
                dataset, candidate, train_origins, horizons, executor
            )
            all_traces.extend(traces)
            reasons = promotion_reasons(
                metrics,
                incumbent_metrics,
                min_skill_gain,
                max_coverage_regression,
            )
            record = {
                "generation": generation,
                "candidate": candidate.to_dict(),
                "train_metrics": metrics.to_dict(),
                "promotion_gate": {"passed": not reasons, "reasons": reasons},
            }
            experiments.append(record)
            status = "eligible" if not reasons else "rejected"
            print(
                f"g{generation} {candidate.candidate_id}: skill={metrics.skill:.4f} "
                f"coverage={metrics.coverage_80:.3f} [{status}]"
            )
            if not reasons:
                eligible.append((candidate, metrics))
        if eligible:
            incumbent, incumbent_metrics = min(eligible, key=lambda item: item[1].pinball)
            lineage.append(incumbent.candidate_id)
            print(f"promoted -> {incumbent.candidate_id}")
        else:
            print(f"generation {generation}: no promotion")

    heldout_metrics, heldout_traces, _ = evaluate_candidate(
        dataset, incumbent, heldout_origins, horizons, executor
    )
    all_traces.extend(heldout_traces)
    cutoff_request = dataset.history_request(cutoff, horizons, incumbent.to_dict())
    cutoff_result = executor.execute(cutoff_request)
    all_traces.append(
        {
            "event": "cutoff_forecast_completed",
            "candidate_id": incumbent.candidate_id,
            "origin": cutoff,
            "request_sha256": cutoff_result.request_sha256,
            "backend": cutoff_result.backend,
            "duration_seconds": round(cutoff_result.duration_seconds, 6),
            "forecast_rows": len(cutoff_result.rows),
        }
    )

    run = {
        "schema_version": 1,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "git_commit": _git_commit(),
        "seed": seed,
        "data": dataset.manifest(),
        "executor_policy": executor.policy(),
        "experiment_contract": {
            "train_origins": train_origins,
            "heldout_origins": heldout_origins,
            "cutoff": cutoff,
            "horizons": horizons,
            "generations": generations,
            "candidates_per_generation": candidates_per_generation,
            "min_skill_gain": min_skill_gain,
            "max_coverage_regression": max_coverage_regression,
            "heldout_used_for_selection": False,
        },
        "champion": incumbent.to_dict(),
        "lineage": lineage,
        "train_metrics": incumbent_metrics.to_dict(),
        "heldout_metrics": heldout_metrics.to_dict(),
        "experiments": experiments,
        "outputs": {
            "forecast": f"forecast_{cutoff}.csv",
            "trace": "trace.jsonl",
        },
    }
    with (output_dir / "run.json").open("w", encoding="utf-8") as handle:
        json.dump(_json_safe(run), handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    with (output_dir / "trace.jsonl").open("w", encoding="utf-8") as handle:
        for event in all_traces:
            handle.write(json.dumps(_json_safe(event), sort_keys=True, allow_nan=False) + "\n")
    _write_forecast(output_dir / f"forecast_{cutoff}.csv", cutoff_result.rows, incumbent)
    print(
        f"held-out: skill={heldout_metrics.skill:.4f} coverage={heldout_metrics.coverage_80:.3f} "
        f"cells={heldout_metrics.n_cells}"
    )
    print(f"wrote {output_dir / 'run.json'}")
    return run
