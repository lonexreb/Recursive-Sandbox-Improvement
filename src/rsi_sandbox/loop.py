from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import evaluation
from .data import Dataset, day_of, iso, sha256_file
from .evaluation import evaluate_forecasts
from .executors import ExecutionError, ExecutionResult, Executor, FailureKind
from .models import CandidateConfig, ForecastRow, Metrics, canonical_json
from .proposer import BoundedProposer, signature
from .splits import SplitSpec

Propose = Callable[[CandidateConfig, int, int, set], list[CandidateConfig]]


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
    """Run one candidate over origins; an infrastructure failure is retried at most once."""

    traces: list[dict[str, Any]] = []
    forecasts: list[tuple[str, list[ForecastRow]]] = []
    for origin in origins:
        request = dataset.history_request(origin, horizons, candidate.to_dict())
        for attempt in (1, 2):
            try:
                result: ExecutionResult = executor.execute(request)
                break
            except Exception as exc:
                infra = FailureKind.INFRASTRUCTURE_FAILURE
                kind = exc.kind if isinstance(exc, ExecutionError) else infra
                event = {"candidate_id": candidate.candidate_id, "origin": origin}
                event |= {"failure_kind": kind.value, "attempt": attempt}
                if kind is infra and attempt == 1:
                    traces.append({"event": "infra_retry", **event})
                    continue
                # host-side trace only; proposers see just the typed kind
                traces.append({"event": "experiment_failed", **event, "error": str(exc)[:300]})
                return _failure_metrics(f"execution failure: {kind.value}"), traces, forecasts
        forecasts.append((origin, result.rows))
        traces.append(
            {
                "event": "experiment_completed",
                "candidate_id": candidate.candidate_id,
                "origin": origin,
                "request_sha256": result.request_sha256,
                "response_sha256": result.response_sha256,
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


def _git(*args: str) -> str | None:
    root = Path(__file__).resolve().parents[2]
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *args], text=True, stderr=subprocess.DEVNULL
        )
    except (OSError, subprocess.CalledProcessError):
        return None


def provenance() -> dict[str, Any]:
    """Source identity: commit, dirty-tree state/hash and scorer SHA-256."""

    commit, status, diff = _git("rev-parse", "HEAD"), _git("status", "--porcelain"), _git("diff")
    return {
        "git_commit": commit.strip() if commit else None,
        "git_dirty": None if status is None else bool(status.strip()),
        "git_dirty_sha256": hashlib.sha256(f"{status}\n{diff}".encode()).hexdigest(),
        "scorer_sha256": sha256_file(Path(evaluation.__file__)),
    }


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


def run_search(
    dataset: Dataset,
    executor: Executor,
    splits: SplitSpec,
    propose: Propose,
    generations: int,
    candidates_per_generation: int,
    min_skill_gain: float = 0.002,
    max_coverage_regression: float = 0.05,
    log: Callable[[str], None] = lambda _message: None,
) -> dict[str, Any]:
    """Train screens, validation (when given) promotes, held-out runs once at the end.

    Every candidate is charged its full slot (train + validation origins) even when it
    fails early, so arms with different failure rates still consume equal budgets.
    """

    splits.validate()  # before any executor activity
    phases = [("train", list(splits.train)), ("validation", list(splits.validation))]
    phases = [(name, origins) for name, origins in phases if origins]
    gate = phases[-1][0]
    traces: list[dict[str, Any]] = []
    charged = 0

    def evaluate(candidate: CandidateConfig) -> dict[str, Metrics]:
        nonlocal charged
        charged += sum(len(origins) for _, origins in phases)
        scored: dict[str, Metrics] = {}
        for name, origins in phases:
            scored[name], new_traces, _ = evaluate_candidate(
                dataset, candidate, origins, splits.horizons, executor
            )
            traces.extend(new_traces)
            if not scored[name].valid:
                break
        return scored

    incumbent = CandidateConfig(name="flat-last-value")
    seen = {signature(incumbent)}
    experiments: list[dict[str, Any]] = []
    lineage = [incumbent.candidate_id]
    incumbent_metrics = evaluate(incumbent)
    failed = [m for m in incumbent_metrics.values() if not m.valid]
    if failed:
        raise RuntimeError(f"incumbent evaluation failed: {failed[0].violations[:3]}")

    for generation in range(1, generations + 1):
        proposals = propose(incumbent, generation, candidates_per_generation, seen)
        eligible: list[tuple[CandidateConfig, dict[str, Metrics]]] = []
        for candidate in proposals:
            seen.add(signature(candidate))
            metrics = evaluate(candidate)
            decisive = metrics.get(gate, metrics["train"])  # train failure stops before gate
            reasons = promotion_reasons(
                decisive, incumbent_metrics[gate], min_skill_gain, max_coverage_regression
            )
            record: dict[str, Any] = {
                "generation": generation,
                "candidate": candidate.to_dict(),
                "train_metrics": metrics["train"].to_dict(),
                "promotion_gate": {"passed": not reasons, "reasons": reasons},
            }
            experiments.append(record)
            status = "eligible" if not reasons else "rejected"
            log(
                f"g{generation} {candidate.candidate_id}: skill={decisive.skill:.4f} "
                f"coverage={decisive.coverage_80:.3f} [{status}]"
            )
            if not reasons:
                eligible.append((candidate, metrics))
        if eligible:
            incumbent, incumbent_metrics = min(eligible, key=lambda item: item[1][gate].pinball)
            lineage.append(incumbent.candidate_id)
            log(f"promoted -> {incumbent.candidate_id}")

    events = Counter(t["event"] for t in traces)
    ledger = {
        "charged_attempts": charged,
        "executed_attempts": events["experiment_completed"] + events["experiment_failed"],
        "infra_retries": events["infra_retry"],
        "failures": dict(
            Counter(t["failure_kind"] for t in traces if t["event"] == "experiment_failed")
        ),
        "heldout_attempts": len(splits.heldout),
    }
    # Held-out is touched exactly once, after the last promotion decision.
    heldout_metrics, heldout_traces, _ = evaluate_candidate(
        dataset, incumbent, list(splits.heldout), splits.horizons, executor
    )
    return {
        "champion": incumbent,
        "lineage": lineage,
        "train_metrics": incumbent_metrics["train"],
        "validation_metrics": incumbent_metrics.get("validation"),
        "heldout_metrics": heldout_metrics,
        "experiments": experiments,
        "traces": traces + heldout_traces,
        "ledger": ledger,
    }


def _persist(output_dir: Path, run: dict[str, Any], traces: list[dict[str, Any]]) -> None:
    with (output_dir / "run.json").open("w", encoding="utf-8") as handle:
        json.dump(_json_safe(run), handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    with (output_dir / "trace.jsonl").open("w", encoding="utf-8") as handle:
        for event in traces:
            handle.write(json.dumps(_json_safe(event), sort_keys=True, allow_nan=False) + "\n")


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
    splits = SplitSpec(
        tuple(train_origins), (), tuple(heldout_origins), tuple(horizons), max(horizons)
    ).validate()
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"data: {len(dataset.series)} series | sha256 {dataset.source_sha256[:12]}")
    print(f"backend: {executor.name} | train origins: {', '.join(train_origins)}")
    search = run_search(
        dataset,
        executor,
        splits,
        BoundedProposer(seed=seed).propose,
        generations,
        candidates_per_generation,
        min_skill_gain,
        max_coverage_regression,
        log=print,
    )
    incumbent: CandidateConfig = search["champion"]
    heldout_metrics: Metrics = search["heldout_metrics"]
    all_traces: list[dict[str, Any]] = search["traces"]
    contract = {
        "train_origins": train_origins,
        "heldout_origins": heldout_origins,
        "cutoff": cutoff,
        "horizons": horizons,
        "generations": generations,
        "candidates_per_generation": candidates_per_generation,
        "min_skill_gain": min_skill_gain,
        "max_coverage_regression": max_coverage_regression,
        "heldout_used_for_selection": False,
    }
    prov = provenance()
    run = {
        "schema_version": 1,
        "status": "heldout_complete_cutoff_pending",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "git_commit": prov["git_commit"],
        "provenance": prov,
        "config_sha256": hashlib.sha256(canonical_json(_json_safe(contract)).encode()).hexdigest(),
        "seed": seed,
        "data": dataset.manifest(),
        "executor_policy": executor.policy(),
        "experiment_contract": contract,
        "champion": incumbent.to_dict(),
        "lineage": search["lineage"],
        "train_metrics": search["train_metrics"].to_dict(),
        "heldout_metrics": heldout_metrics.to_dict(),
        "experiments": search["experiments"],
        "ledger": search["ledger"],
        "outputs": {"trace": "trace.jsonl"},
    }
    # Persist the already-computed held-out result before the cutoff forecast can fail.
    _persist(output_dir, run, all_traces)

    try:
        cutoff_result = executor.execute(
            dataset.history_request(cutoff, horizons, incumbent.to_dict())
        )
    except Exception as exc:
        kind = exc.kind if isinstance(exc, ExecutionError) else FailureKind.INFRASTRUCTURE_FAILURE
        run["status"], run["cutoff_failure_kind"] = "cutoff_forecast_failed", kind.value
        _persist(output_dir, run, all_traces)
        raise
    all_traces.append(
        {
            "event": "cutoff_forecast_completed",
            "candidate_id": incumbent.candidate_id,
            "origin": cutoff,
            "request_sha256": cutoff_result.request_sha256,
            "response_sha256": cutoff_result.response_sha256,
            "backend": cutoff_result.backend,
            "duration_seconds": round(cutoff_result.duration_seconds, 6),
            "forecast_rows": len(cutoff_result.rows),
        }
    )
    run["status"], run["outputs"]["forecast"] = "complete", f"forecast_{cutoff}.csv"
    _write_forecast(output_dir / f"forecast_{cutoff}.csv", cutoff_result.rows, incumbent)
    _persist(output_dir, run, all_traces)
    print(
        f"held-out: skill={heldout_metrics.skill:.4f} coverage={heldout_metrics.coverage_80:.3f} "
        f"cells={heldout_metrics.n_cells}"
    )
    print(f"wrote {output_dir / 'run.json'}")
    return run
