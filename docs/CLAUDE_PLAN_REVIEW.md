# Claude Code review of the deep research plan

Review mode: read-only; Claude Code 2.1.325, Sonnet, high effort

## Verdict

**Direction is right, but not executable as written.** Doing declarative work before code
patches is the right order, and the invariants are respected. The first slice is still too
broad, and it skips defects that make H1 unidentifiable and the boundary unenforced. Do not
build the archive, `costs.py`, the `attacks/` package, or the AST yet.

## Five critical flaws

### 1. H1 cannot be identified with the current proposer

- `proposer.py` puts eight seed configurations first. With the defaults, nearly every
  evaluated candidate comes from that fixed grid and mutations are barely reached.
- Multi-seed runs would therefore show little real proposal variance.
- The full grammar has only 4,200 points, making exhaustive/grid search a relevant oracle.
- A valid control needs the same generation structure and budget while ignoring the current
  champion; otherwise the comparison does not isolate inheritance.

### 2. “Held-out revealed once” is unenforceable and the current holdout is burned

- `heldout_used_for_selection: False` is a hardcoded manifest literal.
- The loop does not itself enforce disjointness, ordering, or a maximum-horizon embargo.
- The committed +0.0513 held-out result is now known and cannot be a fresh confirmation set.
- Promotion currently uses the same origins that drive proposals, with no validation split
  or noise model for the fixed minimum skill gain.

### 3. Equal budget is undefined

- Candidate executions, sandbox-seconds, dollars, and wall time are different budgets and
  cannot all be equalized simultaneously.
- Failed candidates fail fast and therefore consume less work than successful candidates.
- The proposer can return fewer candidates than requested, silently shrinking a treatment.
- Candidate failures and Modal infrastructure failures currently share one exception path.
- Modal dollars are modeled rather than directly returned to the caller.

### 4. The statistics are underpowered and confounded

- Rolling folds, horizons, series, and GPU markets are correlated; naive bootstrap units
  overstate the independent sample size.
- “Practically negligible” needs a preregistered effect-size threshold.
- Pooled USD pinball is dominated by high-priced GPUs; normalized/per-series analysis is
  needed alongside the official pooled metric.
- H2/H5 do not specify a code-patch proposer or its proposal cost.
- Archive-arm multiplicity and novelty descriptors are undefined.

### 5. Security sequencing is wrong and some attack-table expectations are false

- `LocalExecutor` shares the user, open network, filesystem, and readable working tree; it
  cannot validate filesystem, network, resource, or persistence isolation.
- `ModalExecutor.add_local_python_source("rsi_sandbox")` ships trusted modules including
  evaluator and orchestration source into the candidate image. This contradicts the proposed
  claim that the scorer is absent, even though future truth is still absent.

## Leakage and security gaps

- Modal process exit status is not checked after `sandbox.wait()`.
- Local and Modal output are read fully before the 5 MB check, exposing orchestrator memory.
- Raw candidate error/stderr strings can enter traces and become a covert/prompt-injection
  channel for a future LLM proposer; proposer feedback should be typed.
- Missing-cell violations reveal truth availability and must stay out of proposer views.
- A cutoff-forecast exception occurs after held-out evaluation but before `run.json`, spending
  holdout evidence without preserving the result.
- Archives must be namespaced by study/fold/seed/arm. Outer/transfer scores need a sealed
  ledger and must never be visible through the proposer interface.
- Provenance lacks dirty-tree state, config/scorer/lock/image hashes, and response hashes.
- Current tests do not cover executor failure modes, split integrity, held-out ordering, or
  pinned Modal policy arguments.

## Revised smallest useful slice

Goal: make “does champion-conditioning beat the same search without it at equal candidate
execution budget?” testable without expanding the mutation surface.

| File | Approx. source lines | Change |
| --- | ---: | --- |
| `splits.py` | 70 | Frozen split model, expanding-window builder, disjoint/order/embargo checks, spec hash |
| `loop.py` | 60 | Enforce splits before execution; optional validation/proposer; provenance; preserve held-out record on cutoff failure |
| `executors.py` | 60 | Typed failures, Modal exit check, capped output, local CPU/stdout limits |
| `proposer.py` | 35 | Optional fixed seeds plus champion-independent grammar sampler |
| `study.py` | 150 | Exact execution budget, three arms, paired fold difference and stdlib permutation test |
| `synthetic.py` | 40 | Deterministic planted-effect and null datasets |
| `cli.py` | 25 | Add `study` without changing `improve` |

The trusted evaluation logic, quantile validation, history truncation, and Modal policy must
stay unchanged and be pinned by tests.

## Acceptance tests

1. Invalid overlap, ordering, or embargo fails before the first executor call.
2. Held-out origins run only after the last promotion and exactly once per arm.
3. Perturbing truth after training leaves candidate requests, lineage, training metrics, and
   validation metrics byte-identical; only held-out metrics may change.
4. Arms receive equal candidate-origin execution budgets, including charged failures, or the
   study is invalid.
5. Timeout, non-zero exit, oversized output, candidate failure, and infrastructure failure
   have distinct typed outcomes. Valid JSON followed by non-zero exit is rejected.
6. A fake Modal module pins blocked networking, no secrets/volumes, gVisor, resource limits,
   and timeouts. Study specs cannot contain resource-control keys.
7. Local tests cover only claims local execution can prove. Network and persistence tests are
   opt-in Modal tests and cannot be used as local security evidence.
8. Same seed/spec results are reproducible apart from time/duration fields and include dirty
   state plus config/scorer/response hashes.
9. Champion-conditioned search wins a planted synthetic; pure-null studies show near-zero
   paired difference and no more than 10% false positives over roughly 20 null studies.

## Stop conditions

Stop before archive/AST work if any of the following occurs:

- held-out ordering or non-interference fails;
- exact execution accounting cannot be achieved;
- null false-positive rate exceeds 10%;
- different seeds still produce identical proposals;
- recursive-minus-control confidence interval contains zero on adequate fresh folds;
- the change modifies trusted evaluation or history filtering;
- implementation exceeds roughly 500 net new production-source lines.

Before any new real-data claim, commit a fresh confirmation block and its study hash. Treat
the existing held-out set as development evidence only.

## Deferrals

Defer content-addressed archives, typed candidate ASTs, code patches, snapshots, a separate
cost package, a large attack package, family-transfer studies, research-memory arms, novelty
selection, dollar claims, and scorer parity. These become justified only after H1 is
identifiable and supported.

## Recommended execution order

1. Add split validation and tests; wire it before all executor calls.
2. Add typed/capped executor failures, Modal exit checks, and fake-Modal policy tests.
3. Make proposer seeding optional and add a champion-independent grammar sampler.
4. Add validation origins, provenance, holdout-order tests, and cutoff-failure preservation.
5. Add synthetic datasets, exact-budget study arms, a CLI entry point, and calibration tests.
6. Run the full test/lint suite and existing local demo; confirm existing `improve` behavior
   and committed forecast artifacts remain unchanged.

