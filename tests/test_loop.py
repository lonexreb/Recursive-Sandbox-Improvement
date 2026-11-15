import csv
import json

import pytest
from support import InProcessExecutor

from rsi_sandbox.data import day_of
from rsi_sandbox.executors import ExecutionError, FailureKind
from rsi_sandbox.loop import run_improvement, run_search
from rsi_sandbox.proposer import BoundedProposer
from rsi_sandbox.splits import SplitSpec
from rsi_sandbox.synthetic import synthetic_dataset

DATASET = synthetic_dataset("planted", 0, n_series=3, days=260)
SPLIT = SplitSpec(
    train=("2026-05-01", "2026-05-08", "2026-05-15"),
    validation=("2026-05-29", "2026-06-05"),
    heldout=("2026-06-19", "2026-06-26"),
    horizons=(1, 3, 7),
    embargo_days=7,
).validate()


class Spy(InProcessExecutor):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.log: list[tuple[str, str]] = []

    def execute(self, request):
        self.log.append((request["origin_date"], request["candidate"]["candidate_id"]))
        return super().execute(request)


def test_heldout_runs_once_after_every_promotion_decision() -> None:
    spy = Spy()
    result = run_search(DATASET, spy, SPLIT, BoundedProposer().propose, 2, 3)
    origins = [origin for origin, _ in spy.log]
    first_heldout = next(i for i, o in enumerate(origins) if o in SPLIT.heldout)
    assert all(o not in SPLIT.heldout for o in origins[:first_heldout])
    held = spy.log[first_heldout:]
    assert [o for o, _ in held] == list(SPLIT.heldout)  # exactly once each
    assert {c for _, c in held} == {result["champion"].candidate_id}
    ledger = result["ledger"]
    assert ledger["charged_attempts"] == 7 * 5
    assert ledger["heldout_attempts"] == 2


def test_validation_drives_promotion_and_is_recorded() -> None:
    result = run_search(DATASET, InProcessExecutor(), SPLIT, BoundedProposer().propose, 2, 3)
    assert result["validation_metrics"] is not None
    assert all(len(e["train_metrics"]["violations"]) == 0 for e in result["experiments"])


def test_infra_failure_retries_once_but_candidate_failure_does_not() -> None:
    state = {"calls": 0}

    def flaky(request):
        state["calls"] += 1
        return FailureKind.INFRASTRUCTURE_FAILURE if state["calls"] == 1 else None

    result = run_search(
        DATASET, InProcessExecutor(fail=flaky), SPLIT, BoundedProposer().propose, 1, 1
    )
    assert result["ledger"]["infra_retries"] == 1
    assert result["ledger"]["failures"] == {}

    bad = InProcessExecutor(fail=lambda r: FailureKind.INFRASTRUCTURE_FAILURE)
    with pytest.raises(RuntimeError, match="incumbent evaluation failed"):
        run_search(DATASET, bad, SPLIT, BoundedProposer().propose, 1, 1)


def test_candidate_failures_are_typed_and_charged() -> None:
    def fail_short_lookback(request):
        return (
            FailureKind.CANDIDATE_FAILURE if request["candidate"]["lookback_days"] == 90 else None
        )

    executor = InProcessExecutor(fail=fail_short_lookback)
    result = run_search(DATASET, executor, SPLIT, BoundedProposer().propose, 1, 4)
    assert result["ledger"]["failures"] == {"candidate_failure": 1}
    assert result["ledger"]["charged_attempts"] == 5 * 5
    assert result["ledger"]["executed_attempts"] < 5 * 5  # the failed slot is forfeited, not free
    failed = [e for e in result["experiments"] if not e["promotion_gate"]["passed"]]
    assert any("candidate failed" in r for e in failed for r in e["promotion_gate"]["reasons"])
    violations = [v for e in result["experiments"] for v in e["train_metrics"]["violations"]]
    assert violations == ["execution failure: candidate_failure"]


def test_future_truth_cannot_reach_requests_proposals_or_validation() -> None:
    cutoff = day_of(SPLIT.validation[-1]) + 7
    perturbed = synthetic_dataset("planted", 0, n_series=3, days=260)
    for points in perturbed.series.values():
        for index, point in enumerate(points):
            if point.day > cutoff:
                points[index] = type(point)(day=point.day, value=point.value * 3.0)

    runs = []
    for dataset in (DATASET, perturbed):
        spy = Spy()
        runs.append((spy, run_search(dataset, spy, SPLIT, BoundedProposer().propose, 2, 3)))
    (spy_a, a), (spy_b, b) = runs
    visible = set(SPLIT.train) | set(SPLIT.validation)

    def requests(spy):
        return [r for r in spy.requests if r["origin_date"] in visible]

    assert json.dumps(requests(spy_a), sort_keys=True) == json.dumps(
        requests(spy_b), sort_keys=True
    )
    assert a["lineage"] == b["lineage"]
    assert a["train_metrics"] == b["train_metrics"]
    assert a["validation_metrics"] == b["validation_metrics"]
    assert a["experiments"] == b["experiments"]
    assert a["heldout_metrics"] != b["heldout_metrics"]  # only held-out may change


def test_improve_writes_provenance_and_hashes(tmp_path) -> None:
    run = run_improvement(
        DATASET,
        InProcessExecutor(),
        tmp_path,
        list(SPLIT.train),
        list(SPLIT.heldout),
        "2026-07-01",
        generations=1,
        candidates_per_generation=2,
    )
    saved = json.loads((tmp_path / "run.json").read_text())
    assert saved["status"] == "complete" == run["status"]
    for key in ("git_commit", "git_dirty", "scorer_sha256", "git_dirty_sha256"):
        assert key in saved["provenance"]
    assert len(saved["config_sha256"]) == 64
    traces = [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]
    done = [t for t in traces if t["event"] == "experiment_completed"]
    assert all(len(t["request_sha256"]) == len(t["response_sha256"]) == 64 for t in done)
    rows = list(csv.DictReader((tmp_path / "forecast_2026-07-01.csv").open()))
    assert rows and all(0 < float(r["q10"]) <= float(r["q50"]) <= float(r["q90"]) for r in rows)


def test_cutoff_failure_cannot_erase_heldout_results(tmp_path) -> None:
    cutoff = "2026-07-01"
    executor = InProcessExecutor(
        fail=lambda r: FailureKind.TIMEOUT if r["origin_date"] == cutoff else None
    )
    with pytest.raises(ExecutionError):
        run_improvement(
            DATASET,
            executor,
            tmp_path,
            list(SPLIT.train),
            list(SPLIT.heldout),
            cutoff,
            generations=1,
            candidates_per_generation=2,
        )
    saved = json.loads((tmp_path / "run.json").read_text())
    assert saved["status"] == "cutoff_forecast_failed"
    assert saved["cutoff_failure_kind"] == "timeout"
    assert saved["heldout_metrics"]["n_cells"] > 0
    assert not list(tmp_path.glob("forecast_*.csv"))
