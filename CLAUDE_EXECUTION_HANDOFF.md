# Claude Code execution handoff

## Objective

Implement the smallest defensible research-harness slice from
`docs/CLAUDE_PLAN_REVIEW.md`: make champion-conditioned search comparable with a
champion-independent control under exact candidate-origin execution budgets, while enforcing
split integrity and hardening executor failure handling.

This is research infrastructure, not permission to add arbitrary code self-modification.

## Branch and authority

- Work only on the current branch: `claude/deep-research-execution`.
- You may create and edit repository source, tests, and docs needed by this handoff.
- Do not commit, push, open a PR, browse the web, invoke remote Modal resources, install new
  dependencies, read credentials, or modify files outside this repository.
- Do not modify `src/rsi_sandbox/evaluation.py` or the filtering behavior of
  `Dataset.history_request` in `data.py`.
- Do not weaken or parameterize Modal's blocked networking, empty secrets/volumes, gVisor,
  resource limits, or timeouts.
- Preserve `rsi-sandbox improve` defaults and committed demo behavior.
- Keep net new production source at or below roughly 500 lines. Tests and docs are excluded.

## Required implementation

### 1. Split contract

Add `src/rsi_sandbox/splits.py` with:

- an immutable split/study-spec representation;
- canonical serialization and SHA-256;
- disjoint train/validation/held-out origins;
- strict chronological ordering;
- an embargo of at least `max(horizons)` between phases;
- rejection of unknown keys and resource-policy knobs;
- validation callable before any executor activity.

Wire validation into the loop before its first candidate execution. Existing callers without
an explicit validation set must keep working through a backward-compatible path.

### 2. Typed executor failures and bounded output

In `executors.py`:

- introduce `ExecutionError` with a small enum-like set: timeout, nonzero exit,
  output-too-large, candidate failure, and infrastructure failure;
- check Modal process exit status even when stdout contains valid JSON;
- cap stdout/stderr while reading rather than after unbounded accumulation where supported;
- preserve existing Modal policy arguments exactly;
- add reasonable local CPU/output limits without claiming local network/filesystem isolation;
- record response SHA-256 on successful executions.

Candidate-visible feedback must be typed; do not feed raw stderr, missing truth keys, or host
paths into a proposer.

### 3. Identifiable proposal control

In `proposer.py`:

- preserve current default seed-first behavior;
- add an explicit mode that skips fixed seeds so mutations are actually exercised;
- add a deterministic, champion-independent sampler over the same 4,200-point grammar,
  without replacement for a study arm;
- guarantee requested proposal count or fail the study explicitly;
- prove different seeds produce different proposals.

### 4. Exact-budget study runner

Add `src/rsi_sandbox/study.py` and a `study` CLI path that:

- compares flat, champion-conditioned recursive, and champion-independent control arms;
- counts candidate-origin execution attempts as the preregistered primary budget;
- charges candidate failures against the budget; separately classifies infrastructure
  failures and allows at most one retry;
- invalidates unequal-budget comparisons rather than normalizing them after the fact;
- uses training for proposals, validation for promotion, and sealed held-out only after the
  lineage is frozen;
- prevents outer/held-out metrics from entering proposer-visible objects;
- computes a paired fold difference and a deterministic stdlib block/permutation test;
- emits a canonical study manifest/result with config, scorer, response, git commit, and
  dirty-tree hashes/state.

Do not claim measured Modal dollars. Candidate-origin attempts are the primary budget.

### 5. Synthetic calibration

Add `src/rsi_sandbox/synthetic.py` with deterministic datasets for:

- a planted regime where champion-conditioned mutations should have an advantage;
- a pure null where recursive and independent search should have no systematic difference.

Synthetic generation must use only data available before each origin and must not special-case
candidate IDs in the evaluator or executor.

### 6. Held-out preservation and provenance

- Ensure a cutoff forecast failure cannot erase already-computed held-out results. Persist a
  partial/failure run record first or use an equivalent atomic approach.
- Record dirty-tree state, canonical config SHA, scorer SHA, lockfile SHA when present,
  request SHA, response SHA, and typed failure kind.
- Label the committed 2026 held-out artifact as development/burned evidence in documentation;
  do not make a new real-data claim in this task.

## Required tests

At minimum add tests proving:

1. overlap, reversal, missing embargo, and unknown/resource keys fail before executor calls;
2. held-out execution occurs after all promotions and once per arm;
3. future-truth perturbation cannot change requests, proposals, lineage, train, or validation;
4. all arms consume exactly equal attempt budgets, including candidate failures;
5. executor failure taxonomy, valid-JSON/nonzero-exit rejection, and capped-output behavior;
6. Modal creation arguments remain pinned through a fake Modal module—no live Modal call;
7. same seed/spec reproducibility and different-seed proposal diversity;
8. planted synthetic advantage and calibration over approximately 20 null studies with a
   false-positive rate no higher than 10%;
9. existing tests and the existing `improve` command remain green.

Tests may mark live network/persistence isolation as `modal`; do not claim those properties
from local tests.

## Verification commands

Run these before returning:

```bash
uv run ruff format .
uv run ruff check .
uv run pytest
uv run rsi-sandbox improve \
  --pack /Users/shubhankar/Downloads/gpu-price-pack-v0.1.1-handover \
  --backend local \
  --generations 1 \
  --candidates-per-generation 2 \
  --out artifacts/local/claude-regression-smoke
git diff --check
git status --short
```

If the external data pack is unavailable, report that check as skipped; do not fabricate it.

## Stop conditions

Stop and report instead of broadening scope if:

- a required invariant needs changes to the trusted evaluator or history filter;
- exact attempt budgets cannot be made equal;
- null false-positive rate exceeds 10%;
- seeded studies are not reproducible or different seeds remain identical;
- the production diff exceeds roughly 500 net new lines;
- existing `improve` behavior or forecast rows change;
- a required Modal exit-code property cannot be verified against the installed SDK.

## Return format

Return a concise implementation report containing:

- files changed and key design decisions;
- production lines added;
- tests and smoke results;
- any stopped/deferred item and why;
- exact `git status --short` output;
- no claim beyond the evidence produced.

