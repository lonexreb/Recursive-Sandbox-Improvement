from __future__ import annotations

import random

from .models import CandidateConfig


def _signature(candidate: CandidateConfig) -> tuple[int, int, int, float, float]:
    return (
        candidate.lookback_days,
        candidate.min_samples,
        candidate.recency_half_life_days,
        candidate.drift_scale,
        candidate.interval_scale,
    )


class BoundedProposer:
    """Deterministic mutations over the finite candidate grammar."""

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

    def __init__(self, seed: int = 7) -> None:
        self.seed = seed

    def propose(
        self,
        champion: CandidateConfig,
        generation: int,
        count: int,
        seen: set[tuple[int, int, int, float, float]],
    ) -> list[CandidateConfig]:
        rng = random.Random(f"{self.seed}:{generation}:{champion.candidate_id}")
        choices = list(self.SEEDS)
        center = _signature(champion)
        dimensions = [
            (0, 30, 45, 60, 90, 120, 180),
            (5, 8, 12, 20),
            (0, 14, 30, 45, 60, 90),
            (0.0, 0.25, 0.5, 0.75, 1.0),
            (0.0, 0.75, 1.0, 1.25, 1.5),
        ]
        for _ in range(40):
            mutation = list(center)
            first = rng.randrange(len(dimensions))
            mutation[first] = rng.choice(dimensions[first])
            if rng.random() < 0.35:
                second = rng.randrange(len(dimensions))
                mutation[second] = rng.choice(dimensions[second])
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
                    parent_id=champion.candidate_id,
                    lookback_days=int(values[0]),
                    min_samples=int(values[1]),
                    recency_half_life_days=int(values[2]),
                    drift_scale=float(values[3]),
                    interval_scale=float(values[4]),
                )
            )
            if len(output) == count:
                break
        return output


def signature(candidate: CandidateConfig) -> tuple[int, int, int, float, float]:
    return _signature(candidate)
