from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any

from .data import day_of, iso
from .models import canonical_json


class SpecError(ValueError):
    """A split or study specification violates the preregistration contract."""


def reject_unknown_keys(value: dict[str, Any], allowed: set[str], where: str) -> None:
    """Allow-list only: resource-policy knobs (timeout, network, ...) are unknown keys."""

    if extra := sorted(set(value) - allowed):
        raise SpecError(f"{where}: keys not allowed: {extra}")


@dataclass(frozen=True)
class SplitSpec:
    """Disjoint, chronological origin phases separated by an embargo."""

    train: tuple[str, ...]
    validation: tuple[str, ...]
    heldout: tuple[str, ...]
    horizons: tuple[int, ...]
    embargo_days: int

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> SplitSpec:
        reject_unknown_keys(value, set(cls.__dataclass_fields__), "split spec")
        return cls(**{k: tuple(v) if isinstance(v, list) else v for k, v in value.items()})

    @property
    def sha256(self) -> str:
        return hashlib.sha256(canonical_json(asdict(self)).encode()).hexdigest()

    def validate(self) -> SplitSpec:
        """Raise SpecError on any contract violation; call before touching an executor."""

        if not self.horizons or min(self.horizons) < 1:
            raise SpecError("horizons must be positive integers")
        if self.embargo_days < max(self.horizons):
            raise SpecError(f"embargo_days {self.embargo_days} < max horizon {max(self.horizons)}")
        days: dict[str, list[int]] = {}
        for name in ("train", "validation", "heldout"):
            origins = getattr(self, name)
            if not origins and name != "validation":
                raise SpecError(f"{name} origins are empty")
            try:
                days[name] = [day_of(origin) for origin in origins]
            except (TypeError, ValueError):
                raise SpecError(f"{name} origins must be ISO dates") from None
            if [iso(day) for day in days[name]] != list(origins):
                raise SpecError(f"{name} origins must be canonical ISO dates")
            if days[name] != sorted(set(days[name])):
                raise SpecError(f"{name} origins must be strictly increasing")
        phases = [name for name in days if days[name]]
        for a, b in zip(phases, phases[1:], strict=False):
            if set(getattr(self, a)) & set(getattr(self, b)):
                raise SpecError(f"{a} and {b} origins overlap")
            if days[b][0] <= days[a][-1]:
                raise SpecError(f"{b} origins must come after {a} origins")
            if days[b][0] - days[a][-1] < self.embargo_days:
                raise SpecError(f"embargo of {self.embargo_days} days missing before {b}")
        return self
