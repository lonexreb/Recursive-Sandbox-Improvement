from dataclasses import asdict

import pytest
from support import InProcessExecutor, build_folds

from rsi_sandbox.loop import run_improvement, run_search
from rsi_sandbox.proposer import BoundedProposer
from rsi_sandbox.splits import SpecError, SplitSpec
from rsi_sandbox.study import StudySpec, run_study
from rsi_sandbox.synthetic import FIRST_ORIGIN, synthetic_dataset

GOOD = SplitSpec(
    train=("2026-05-01", "2026-05-08"),
    validation=("2026-05-22",),
    heldout=("2026-06-05",),
    horizons=(1, 3, 7),
    embargo_days=7,
)


def _with(**changes) -> SplitSpec:
    return SplitSpec(**{**GOOD.__dict__, **changes})


def test_valid_split_has_stable_canonical_hash() -> None:
    assert GOOD.validate() is GOOD
    assert SplitSpec.from_dict(asdict(GOOD)).sha256 == GOOD.sha256
    assert _with(embargo_days=8).sha256 != GOOD.sha256


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"validation": ("2026-05-08",)}, "overlap"),
        ({"validation": ("2026-04-20",)}, "after"),
        ({"validation": ("2026-05-12",)}, "embargo"),
        ({"embargo_days": 3, "validation": ("2026-06-01",)}, "max horizon"),
        ({"train": ("2026-05-08", "2026-05-01")}, "increasing"),
        ({"heldout": ()}, "empty"),
        ({"train": ("2026-5-1",)}, "ISO"),
    ],
)
def test_invalid_splits_are_rejected(changes, message) -> None:
    with pytest.raises(SpecError, match=message):
        _with(**changes).validate()


@pytest.mark.parametrize("key", ["timeout_seconds", "block_network", "memory_mb", "secrets"])
def test_resource_policy_keys_are_rejected(key) -> None:
    with pytest.raises(SpecError, match=f"{key}"):
        SplitSpec.from_dict({**asdict(GOOD), key: 1})
    folds = [asdict(GOOD)]
    with pytest.raises(SpecError, match=f"{key}"):
        StudySpec.from_dict({"folds": folds, "seeds": [1], key: 1})


def test_unknown_keys_are_rejected() -> None:
    with pytest.raises(SpecError, match="surprise"):
        SplitSpec.from_dict({**asdict(GOOD), "surprise": 1})


def test_invalid_split_fails_before_any_executor_call(tmp_path) -> None:
    dataset = synthetic_dataset("null", 0, n_series=2, days=200)
    bad = _with(validation=("2026-05-08",))
    executor = InProcessExecutor()
    with pytest.raises(SpecError):
        run_search(dataset, executor, bad, BoundedProposer().propose, 1, 1)
    with pytest.raises(SpecError):
        run_study(dataset, executor, StudySpec((bad,), (1,)))
    with pytest.raises(SpecError):  # exact test supports at most 14 folds
        run_study(dataset, executor, StudySpec((GOOD,) * 15, (1,)))
    with pytest.raises(SpecError):  # missing embargo between train and heldout (legacy path)
        run_improvement(dataset, executor, tmp_path, ["2026-05-01"], ["2026-05-05"], "2026-06-10")
    assert executor.requests == []


def test_build_folds_are_chronological_and_embargoed() -> None:
    folds = build_folds(FIRST_ORIGIN, 4, (3, 2, 2), 4, (1, 3, 7))
    assert all(fold.embargo_days >= 7 for fold in folds)
    ends = [fold.heldout[-1] for fold in folds]
    starts = [fold.train[0] for fold in folds]
    assert all(end < start for end, start in zip(ends, starts[1:], strict=False))
