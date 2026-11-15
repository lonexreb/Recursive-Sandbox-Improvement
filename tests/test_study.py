import copy
import json

import pytest
from support import InProcessExecutor, build_folds

from rsi_sandbox.data import day_of
from rsi_sandbox.executors import FailureKind
from rsi_sandbox.models import CandidateConfig
from rsi_sandbox.splits import SpecError
from rsi_sandbox.study import ARMS, StudySpec, analyze, make_proposer, run_study, sign_flip_p
from rsi_sandbox.synthetic import FIRST_ORIGIN, synthetic_dataset

HORIZONS = (1, 3, 7)


def _spec(n_folds: int, seeds: tuple[int, ...], generations: int = 2) -> StudySpec:
    folds = build_folds(FIRST_ORIGIN, n_folds, (3, 2, 2), 4, HORIZONS)
    return StudySpec(tuple(folds), seeds, generations)


def test_arms_consume_exactly_equal_budgets_including_failures() -> None:
    dataset = synthetic_dataset("planted", 0, n_series=3, days=210)
    spec = _spec(2, (1, 2))
    executor = InProcessExecutor(
        fail=lambda r: (
            FailureKind.CANDIDATE_FAILURE if r["candidate"]["interval_scale"] == 1.25 else None
        )
    )
    result = run_study(dataset, executor, spec)

    want = spec.expected_attempts(spec.folds[0])
    assert executor.failures, "the failure injector never fired"
    assert {r["ledger"]["charged_attempts"] for r in result["records"]} == {want}
    assert result["analysis"]["valid"] is True
    assert any(r["ledger"]["executed_attempts"] < want for r in result["records"])
    assert all(r["ledger"]["heldout_attempts"] == 2 for r in result["records"])


def test_unequal_budgets_invalidate_instead_of_normalising() -> None:
    dataset = synthetic_dataset("planted", 0, n_series=3, days=210)
    spec = _spec(2, (1,))
    result = run_study(dataset, InProcessExecutor(), spec)
    records = copy.deepcopy(result["records"])
    records[1]["ledger"]["charged_attempts"] += 5
    verdict = analyze(records, spec)
    assert verdict["valid"] is False
    assert "unequal budgets" in verdict["reason"]
    assert "recursive_minus_control" not in verdict


def test_heldout_is_executed_once_per_arm_after_lineage_is_frozen() -> None:
    dataset = synthetic_dataset("planted", 0, n_series=3, days=210)
    spec = _spec(1, (1,))
    executor = InProcessExecutor()
    run_study(dataset, executor, spec)
    fold = spec.folds[0]
    origins = [r["origin_date"] for r in executor.requests]
    for origin in fold.heldout:
        assert origins.count(origin) == len(ARMS)
    per_arm = len(origins) // len(ARMS)
    for arm in range(len(ARMS)):
        block = origins[arm * per_arm : (arm + 1) * per_arm]
        assert block[-len(fold.heldout) :] == list(fold.heldout)
        assert not set(block[: -len(fold.heldout)]) & set(fold.heldout)


def test_proposers_never_see_heldout_data() -> None:
    dataset = synthetic_dataset("planted", 0, n_series=3, days=210)
    spec = _spec(1, (1,))
    seen_args: list[tuple] = []

    def spying_factory(arm, seed):
        inner = make_proposer(arm, seed)

        def propose(champion, generation, count, seen):
            seen_args.append((champion, generation, count, frozenset(seen)))
            return inner(champion, generation, count, seen)

        return propose

    result = run_study(dataset, InProcessExecutor(), spec, proposer_factory=spying_factory)
    blob = repr(seen_args)
    for record in result["records"]:
        assert str(record["sealed_heldout"]["pinball"]) not in blob
    for champion, generation, count, seen in seen_args:  # config, ints, signature tuples only
        assert isinstance(champion, CandidateConfig)
        assert isinstance(generation, int) and isinstance(count, int)
        assert all(isinstance(item, tuple) and len(item) == 5 for item in seen)


def test_unsupported_preregistered_origin_fails_before_executor_activity() -> None:
    dataset = synthetic_dataset("planted", 0, n_series=3, days=60)
    spec = StudySpec(
        folds=(
            type(_spec(1, (1,)).folds[0])(
                train=("2030-01-01",),
                validation=("2030-01-08",),
                heldout=("2030-01-15",),
                horizons=HORIZONS,
                embargo_days=7,
            ),
        ),
        seeds=(1,),
    )
    executor = InProcessExecutor()

    with pytest.raises(SpecError, match="no truth-aligned cells"):
        run_study(dataset, executor, spec)

    assert executor.requests == []


def test_future_truth_changes_only_heldout_study_results() -> None:
    spec = _spec(1, (1,))
    fold = spec.folds[0]
    cutoff = day_of(fold.validation[-1]) + 7
    base = synthetic_dataset("planted", 0, n_series=3, days=210)
    moved = synthetic_dataset("planted", 0, n_series=3, days=210)
    for points in moved.series.values():
        for index, point in enumerate(points):
            if point.day > cutoff:
                points[index] = type(point)(day=point.day, value=point.value * 2.0)
    a = run_study(base, InProcessExecutor(), spec)["records"]
    b = run_study(moved, InProcessExecutor(), spec)["records"]
    for left, right in zip(a, b, strict=True):
        for key in ("champion", "lineage", "train_metrics", "validation_metrics", "ledger"):
            assert left[key] == right[key]
        assert left["sealed_heldout"] != right["sealed_heldout"]


def test_same_spec_and_seed_reproduce_and_seeds_differ() -> None:
    dataset = synthetic_dataset("planted", 0, n_series=3, days=210)
    spec = _spec(2, (1, 2))
    first = run_study(dataset, InProcessExecutor(), spec)
    second = run_study(dataset, InProcessExecutor(), spec)
    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["provenance"]["scorer_sha256"] and "git_dirty" in first["provenance"]
    by_seed = {}
    for record in first["records"]:
        if record["arm"] != "flat" and record["fold"] == 0:
            by_seed.setdefault(record["arm"], {})[record["seed"]] = record["trace_sha256"]
    assert all(len(set(hashes.values())) == 2 for hashes in by_seed.values())


def test_sign_flip_test_is_exact_and_deterministic() -> None:
    assert sign_flip_p([0.0] * 6) == 1.0
    assert sign_flip_p([1.0] * 6) == 2 / 64
    assert sign_flip_p([1.0, -1.0, 1.0, -1.0]) == 1.0
    assert sign_flip_p([3.0, 1.0, 1.0]) == 2 / 8  # only the all-same-sign flips reach |sum|=5


def test_planted_regime_tests_compounding_through_inheritance() -> None:
    """Causal property: the trend makes drift_scale and interval_scale each individually
    beneficial. The control re-mutates the flat anchor every generation, so it plateaus at
    the first beneficial change; the recursive arm inherits the generation-1 champion and
    stacks further changes. Nothing else differs between the arms (same operator, rng
    stream, seen-set and budget), so a gap here is attributable to inheritance."""

    gaps = []
    for data_seed in range(3):
        dataset = synthetic_dataset("planted", data_seed, days=460)
        result = run_study(dataset, InProcessExecutor(), _spec(8, (1, 2), generations=3))
        gap = result["analysis"]["recursive_minus_control"]
        assert gap["p_value_two_sided"] < 0.05
        gaps.append(gap["mean"])
    assert min(gaps) > 0.03


def test_null_studies_are_calibrated_and_near_zero() -> None:
    """Pure-null data (unpredictable shocks): neither arm should lead, in mean or by test."""

    spec = _spec(6, (1,), generations=3)
    gaps, false_positives = [], 0
    for data_seed in range(20):
        dataset = synthetic_dataset("null", data_seed, n_series=4, days=360)
        gap = run_study(dataset, InProcessExecutor(), spec)["analysis"]["recursive_minus_control"]
        gaps.append(gap["mean"])
        false_positives += gap["p_value_two_sided"] < 0.05
    assert false_positives / 20 <= 0.10
    assert abs(sum(gaps) / len(gaps)) <= 0.01  # one skill point; study-to-study sd is ~0.05
