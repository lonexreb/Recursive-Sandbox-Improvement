from __future__ import annotations

import hashlib
import itertools
import statistics
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from .data import Dataset
from .executors import Executor
from .loop import Propose, _json_safe, provenance, run_search
from .models import CandidateConfig, canonical_json
from .proposer import BoundedProposer
from .splits import SpecError, SplitSpec, reject_unknown_keys

ARMS = ("flat", "recursive", "control")


@dataclass(frozen=True)
class StudySpec:
    """Preregistered study: folds, seeds and search budget. No resource knobs exist."""

    folds: tuple[SplitSpec, ...]
    seeds: tuple[int, ...]
    generations: int = 2
    candidates_per_generation: int = 3
    min_skill_gain: float = 0.002
    max_coverage_regression: float = 0.05

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> StudySpec:
        reject_unknown_keys(value, set(cls.__dataclass_fields__), "study spec")
        folds = tuple(SplitSpec.from_dict(fold) for fold in value["folds"])
        return cls(**{**value, "folds": folds, "seeds": tuple(value["seeds"])})

    @property
    def sha256(self) -> str:
        return hashlib.sha256(canonical_json(asdict(self)).encode()).hexdigest()

    def validate(self) -> StudySpec:
        if (
            not 0 < len(self.folds) <= 14
            or not self.seeds
            or len(set(self.seeds)) < len(self.seeds)
        ):
            raise SpecError("study needs 1-14 folds (exact test) and unique seeds")
        if self.generations < 1 or self.candidates_per_generation < 1:
            raise SpecError("generations and candidates_per_generation must be >= 1")
        if len({fold.horizons for fold in self.folds}) != 1:
            raise SpecError("all folds must share horizons")
        for fold in self.folds:
            if not fold.validate().validation:
                raise SpecError("study folds need validation origins")
        return self

    def expected_attempts(self, fold: SplitSpec) -> int:
        """Incumbent plus every proposal, each charged train + validation origins."""

        return (1 + self.generations * self.candidates_per_generation) * (
            len(fold.train) + len(fold.validation)
        )


def make_proposer(arm: str, seed: int) -> Propose:
    flat = CandidateConfig(name="flat-last-value")
    if arm == "flat":  # no search: re-runs the flat config so the attempt ledger matches
        return lambda champion, generation, count, seen: [
            CandidateConfig(name=f"g{generation}-flat-{i}", parent_id=champion.candidate_id)
            for i in range(1, count + 1)
        ]
    # recursive: mutate the evolving champion; control: the same operator, rng stream and
    # budget, anchored on the fixed starting incumbent (ignores the evolving champion).
    anchor = flat if arm == "control" else None
    return BoundedProposer(seed, fixed_seeds=False, strict=True, anchor=anchor).propose


def sign_flip_p(blocks: list[float]) -> float:
    """Exact two-sided paired sign-flip permutation test on block means (<= 14 blocks)."""

    observed = abs(sum(blocks)) - 1e-12
    signs = itertools.product((1, -1), repeat=len(blocks))
    hits = sum(abs(sum(s * b for s, b in zip(c, blocks, strict=True))) >= observed for c in signs)
    return hits / 2 ** len(blocks)


def analyze(records: list[dict[str, Any]], spec: StudySpec) -> dict[str, Any]:
    """Paired fold analysis. Unequal budgets or invalid held-out invalidate; nothing is rescaled."""

    index = {(r["fold"], r["seed"], r["arm"]): r for r in records}
    for f, fold in enumerate(spec.folds):
        want = spec.expected_attempts(fold)
        for seed in spec.seeds:
            cells = {arm: index[(f, seed, arm)] for arm in ARMS}
            charged = {arm: cell["ledger"]["charged_attempts"] for arm, cell in cells.items()}
            if set(charged.values()) != {want}:
                return {"valid": False, "reason": f"unequal budgets {charged}, expected {want}"}
            if not all(cell["sealed_heldout"]["valid"] for cell in cells.values()):
                return {"valid": False, "reason": f"invalid held-out in fold {f} seed {seed}"}
    blocks = [
        statistics.fmean(
            index[(f, s, "recursive")]["sealed_heldout"]["skill"]
            - index[(f, s, "control")]["sealed_heldout"]["skill"]
            for s in spec.seeds
        )
        for f in range(len(spec.folds))
    ]
    return {
        "valid": True,
        "recursive_minus_control": {
            "fold_means": blocks,
            "mean": statistics.fmean(blocks),
            "p_value_two_sided": sign_flip_p(blocks),
            "test": "paired sign-flip over fold means",
        },
    }


def run_study(
    dataset: Dataset,
    executor: Executor,
    spec: StudySpec,
    proposer_factory: Callable[[str, int], Propose] = make_proposer,
) -> dict[str, Any]:
    """Run every (fold, seed, arm); returns the canonical manifest/result with its SHA-256."""

    spec.validate()  # before any executor activity
    records = []
    for f, fold in enumerate(spec.folds):
        for seed in spec.seeds:
            for arm in ARMS:
                search = run_search(
                    dataset,
                    executor,
                    fold,
                    proposer_factory(arm, seed),
                    spec.generations,
                    spec.candidates_per_generation,
                    spec.min_skill_gain,
                    spec.max_coverage_regression,
                )
                chain = [  # durations excluded so equal inputs give equal hashes
                    [t.get(k) for k in ("event", "candidate_id", "origin", "request_sha256")]
                    + [t.get("response_sha256"), t.get("failure_kind")]
                    for t in search["traces"]
                ]
                records.append(
                    {
                        "fold": f,
                        "seed": seed,
                        "arm": arm,
                        "champion": search["champion"].candidate_id,
                        "lineage": search["lineage"],
                        "train_metrics": search["train_metrics"].to_dict(),
                        "validation_metrics": search["validation_metrics"].to_dict(),
                        "ledger": search["ledger"],
                        "trace_sha256": hashlib.sha256(canonical_json(chain).encode()).hexdigest(),
                        # sealed ledger: written after the lineage froze, never given a proposer
                        "sealed_heldout": search["heldout_metrics"].to_dict(),
                    }
                )
    result = _json_safe(
        {
            "schema_version": 1,
            "spec": asdict(spec),
            "spec_sha256": spec.sha256,
            "data": dataset.manifest(),
            "executor_policy": executor.policy(),
            "provenance": provenance(),
            "records": records,
            "analysis": analyze(records, spec),
        }
    )
    result["result_sha256"] = hashlib.sha256(canonical_json(result).encode()).hexdigest()
    return result
