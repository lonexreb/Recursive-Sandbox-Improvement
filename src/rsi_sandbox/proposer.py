from __future__ import annotations

import random

from .models import CandidateConfig

# The complete 7*4*6*5*5 = 4,200-point candidate grammar, in CandidateConfig field order.
DIMENSIONS = (
    (0, 30, 45, 60, 90, 120, 180),
    (5, 8, 12, 20),
    (0, 14, 30, 45, 60, 90),
    (0.0, 0.25, 0.5, 0.75, 1.0),
    (0.0, 0.75, 1.0, 1.25, 1.5),
)


class ProposalShortfall(RuntimeError):
    """The proposer could not return the requested number of new candidates."""


def _signature(candidate: CandidateConfig) -> tuple[int, int, int, float, float]:
    return (
        candidate.lookback_days,
        candidate.min_samples,
        candidate.recency_half_life_days,
        candidate.drift_scale,
        candidate.interval_scale,
    )


class BoundedProposer:
    """Deterministic mutations over the finite candidate grammar.

    `fixed_seeds=False` skips the eight seed configurations so mutations are exercised.
    `strict=True` raises ProposalShortfall instead of returning fewer candidates.
    `anchor` freezes the mutation center (and rng stream) at a fixed candidate: the
    champion-independent control uses the identical mutation operator around the starting
    incumbent, so it differs from the recursive arm only by not inheriting the champion.
    """

    SEEDS = (
        (0, 8, 0, 1.0, 1.0),
        (90, 8, 45, 0.5, 1.0),
        (60, 8, 30, 0.75, 1.0),
        (120, 12, 60, 0.5, 1.25),
        (45, 5, 14, 0.25, 1.25),
        (180, 20, 90, 0.75, 0.75),
        (90, 12, 30, 1.0, 1.5),
        (30, 5, 14, 0.0, 1.0),
    )

    def __init__(
        self,
        seed: int = 7,
        fixed_seeds: bool = True,
        strict: bool = False,
        anchor: CandidateConfig | None = None,
    ) -> None:
        self.seed, self.fixed_seeds, self.strict, self.anchor = seed, fixed_seeds, strict, anchor

    def propose(
        self,
        champion: CandidateConfig,
        generation: int,
        count: int,
        seen: set[tuple[int, int, int, float, float]],
    ) -> list[CandidateConfig]:
        parent = self.anchor or champion
        rng = random.Random(f"{self.seed}:{generation}:{parent.candidate_id}")
        choices = list(self.SEEDS) if self.fixed_seeds else []
        center = _signature(parent)
        for _ in range(40 if self.fixed_seeds else 400):
            mutation = list(center)
            first = rng.randrange(len(DIMENSIONS))
            mutation[first] = rng.choice(DIMENSIONS[first])
            if rng.random() < 0.35:
                second = rng.randrange(len(DIMENSIONS))
                mutation[second] = rng.choice(DIMENSIONS[second])
            choices.append(tuple(mutation))

        output: list[CandidateConfig] = []
        local_seen = set(seen)
        local_seen.add(center)
        for values in choices:
            if values in local_seen:
                continue
            local_seen.add(values)
            index = len(output) + 1
            output.append(
                CandidateConfig(
                    name=f"g{generation}-proposal-{index}",
                    parent_id=parent.candidate_id,
                    lookback_days=int(values[0]),
                    min_samples=int(values[1]),
                    recency_half_life_days=int(values[2]),
                    drift_scale=float(values[3]),
                    interval_scale=float(values[4]),
                )
            )
            if len(output) == count:
                break
        if self.strict and len(output) < count:
            raise ProposalShortfall(f"requested {count} proposals, produced {len(output)}")
        return output


def signature(candidate: CandidateConfig) -> tuple[int, int, int, float, float]:
    return _signature(candidate)
