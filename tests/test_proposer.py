import itertools

import pytest

from rsi_sandbox.models import CandidateConfig
from rsi_sandbox.proposer import DIMENSIONS, BoundedProposer, ProposalShortfall, signature
from rsi_sandbox.study import make_proposer

FLAT = CandidateConfig(name="flat-last-value")
MOVED = CandidateConfig(name="moved", lookback_days=90, drift_scale=0.5, interval_scale=1.0)
SEEN = {signature(FLAT)}


def _sigs(proposals) -> list[tuple]:
    return [signature(p) for p in proposals]


def _distance(a, b) -> int:
    return sum(x != y for x, y in zip(a, b, strict=True))


def test_grammar_has_4200_points() -> None:
    assert len(list(itertools.product(*DIMENSIONS))) == 4200


def test_default_proposer_is_seed_first() -> None:
    proposals = BoundedProposer(seed=7).propose(FLAT, 1, 4, SEEN)
    assert _sigs(proposals) == list(BoundedProposer.SEEDS[:4])
    assert _sigs(proposals) == _sigs(BoundedProposer(seed=99).propose(FLAT, 1, 4, SEEN))


def test_fixed_seeds_can_be_skipped_so_mutations_run() -> None:
    sigs = _sigs(BoundedProposer(seed=7, fixed_seeds=False, strict=True).propose(FLAT, 1, 6, SEEN))
    assert len(sigs) == len(set(sigs)) == 6
    assert sigs != list(BoundedProposer.SEEDS[:6])
    assert all(_distance(sig, signature(FLAT)) <= 2 for sig in sigs)  # local mutations only


def test_same_seed_reproduces_and_different_seeds_diverge() -> None:
    for arm in ("recursive", "control"):
        make = lambda seed, arm=arm: make_proposer(arm, seed)(FLAT, 1, 6, SEEN)  # noqa: E731
        assert _sigs(make(3)) == _sigs(make(3))
        assert _sigs(make(3)) != _sigs(make(4))


def test_strict_proposer_fails_instead_of_shrinking() -> None:
    with pytest.raises(ProposalShortfall):
        BoundedProposer(seed=1, fixed_seeds=False, strict=True).propose(FLAT, 1, 5000, SEEN)
    assert len(BoundedProposer(seed=1, fixed_seeds=False).propose(FLAT, 1, 5000, SEEN)) < 5000


def test_control_ignores_the_evolving_champion() -> None:
    control = make_proposer("control", 5)
    assert _sigs(control(FLAT, 2, 6, SEEN)) == _sigs(control(MOVED, 2, 6, SEEN))
    assert all(_distance(s, signature(FLAT)) <= 2 for s in _sigs(control(MOVED, 2, 6, SEEN)))
    assert {p.parent_id for p in control(MOVED, 2, 6, SEEN)} == {FLAT.candidate_id}


def test_recursive_arm_centers_on_the_champion() -> None:
    recursive = make_proposer("recursive", 5)
    sigs = _sigs(recursive(MOVED, 2, 6, SEEN))
    assert all(_distance(s, signature(MOVED)) <= 2 for s in sigs)
    assert sigs != _sigs(recursive(FLAT, 2, 6, SEEN))


def test_arms_share_the_proposal_operator_while_the_champion_is_unchanged() -> None:
    """Matched control: identical draws until inheritance changes the champion."""

    assert _sigs(make_proposer("recursive", 5)(FLAT, 1, 6, SEEN)) == _sigs(
        make_proposer("control", 5)(FLAT, 1, 6, SEEN)
    )


def test_control_samples_without_replacement_across_generations() -> None:
    control, seen, drawn = make_proposer("control", 5), set(SEEN), []
    for generation in range(1, 4):
        proposals = control(MOVED, generation, 5, seen)
        seen |= set(_sigs(proposals))
        drawn += _sigs(proposals)
    assert len(drawn) == len(set(drawn)) == 15
