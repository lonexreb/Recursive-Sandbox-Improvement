"""Shared test doubles. Nothing here touches Modal or the network."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

from rsi_sandbox.data import day_of, iso
from rsi_sandbox.executors import ExecutionError, ExecutionResult, FailureKind
from rsi_sandbox.forecast import forecast_request
from rsi_sandbox.models import canonical_json
from rsi_sandbox.splits import SplitSpec


class InProcessExecutor:
    """Runs the real forecaster in-process (fast) while recording every request."""

    name = "in-process-test"

    def __init__(self, fail: Callable[[dict[str, Any]], FailureKind | None] | None = None) -> None:
        self.fail = fail
        self.requests: list[dict[str, Any]] = []
        self.failures: list[FailureKind] = []

    def policy(self) -> dict[str, Any]:
        return {"backend": self.name}

    def execute(self, request: dict[str, Any]) -> ExecutionResult:
        self.requests.append(request)
        payload = canonical_json(request)
        kind = self.fail(request) if self.fail else None
        if kind is not None:
            self.failures.append(kind)
            raise ExecutionError(kind, "injected")
        rows = forecast_request(json.loads(payload))
        response = canonical_json([row.to_dict() for row in rows])
        return ExecutionResult(
            rows=rows,
            duration_seconds=0.0,
            backend=self.name,
            request_sha256=hashlib.sha256(payload.encode()).hexdigest(),
            response_sha256=hashlib.sha256(response.encode()).hexdigest(),
        )


def build_folds(first_origin, n_folds, counts, step_days, horizons):
    """Non-overlapping chronological folds; `counts` = (train, validation, heldout) origins."""
    embargo, cursor, folds = max(horizons), day_of(first_origin), []
    for _ in range(n_folds):
        phases = []
        for count in counts:
            days = [cursor + index * step_days for index in range(count)]
            phases.append(tuple(iso(day) for day in days))
            cursor = (days[-1] if days else cursor) + max(step_days, embargo)
        folds.append(SplitSpec(*phases, tuple(horizons), embargo).validate())
    return folds
