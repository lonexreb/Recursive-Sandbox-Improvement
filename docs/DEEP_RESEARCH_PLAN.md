# Deep research plan: from bounded tuning to defensible RSI

Status: draft for independent Claude Code review

## 1. Decision this research must support

Determine whether Recursive Sandbox Improvement should expand from a fixed parameter
grammar into a bounded code-patch system, and under what evidence and security controls a
candidate may recursively become the parent of the next generation.

The research is successful only if it can answer all four questions:

1. **Capability:** does recursive inheritance outperform equally budgeted non-recursive
   search on unseen origins and unseen series groups?
2. **Scientific validity:** do gains survive multiple seeds, nested selection, ablations,
   and the official scorer rather than appearing only on the selection window?
3. **Safety:** can candidate code remain unable to inspect truth, alter evaluation,
   exfiltrate data, enlarge its resource budget, or persist outside its lineage artifact?
4. **Economics:** are the gains worth the full improvement cost, including rejected
   candidates, verification, orchestration, and Modal compute?

The intended outcome is a go/no-go decision for bounded code patches—not a general claim
that open-ended recursive self-improvement has been solved.

## 2. Current baseline and gaps

The shipped system already has a credible minimum boundary:

- one fresh process or Modal gVisor sandbox per `(candidate, origin)`;
- history truncated before candidate execution and truth joined afterward;
- blocked Modal networking, no secrets or volumes, and CPU/RAM/time limits;
- immutable host-side evaluation and promotion policy;
- a finite parameter grammar, lineage, trace hashes, and held-out reporting.

The current positive result (+0.0513 held-out skill in the committed full demo) is useful
engineering evidence but not sufficient RSI evidence. The main gaps are:

- the “proposer” enumerates deterministic parameter mutations rather than generating new
  algorithms or modifying its own research harness;
- one training split, one held-out split, and one seed cannot separate genuine improvement
  from selection noise;
- the champion-only loop has no archive, diversity pressure, or transfer evaluation;
- coverage is reported but not calibrated to the 80% target or tested conditionally;
- cost, rejected-candidate work, and verification overhead are not first-class objectives;
- safety is asserted by configuration but not attacked with adversarial candidates;
- run manifests do not yet provide environment/image identity, failure taxonomy, or a
  replay command that independently reconstructs a result.

## 3. Research hypotheses

Each hypothesis has a falsifiable comparison and a stop condition.

### H1 — recursive inheritance adds value

An archive-based recursive search closes more held-out performance gap than an equally
budgeted random/grid search whose proposals do not inherit accepted artifacts.

- Primary measure: mean held-out skill across at least 10 split/seed combinations.
- Secondary measures: worst-split skill, positive-skill rate, calibration, and variance.
- Falsifier: confidence interval overlaps a practically negligible effect, or the recursive
  method wins only after consuming materially more candidate executions.

### H2 — bounded code patches add value beyond parameter search

Candidates restricted to a narrow forecasting module can discover improvements unavailable
to the existing lookback/drift/interval grammar without changing evaluator behavior.

- Compare parameter-only, declarative feature-composition, and signed code-patch tracks.
- Require transfer to withheld series families and dates not used in proposal selection.
- Falsifier: patch track does not beat the simpler grammar after correction for search cost.

### H3 — an independent host controller prevents evaluator capture

Even malicious candidate patches cannot read future truth, mutate the scorer or limits,
communicate externally, forge provenance, or affect another candidate.

- Run a red-team corpus of explicit leakage, tampering, network, fork-bomb, disk-fill,
  timeout-edit, output-bomb, and cross-origin-state attacks.
- Falsifier: any attack changes a score or promotion decision without a typed refusal.

### H4 — archives improve robustness, not only peak score

A diverse lineage archive with explicit parent selection finds solutions with higher
worst-split performance and lower seed variance than champion-only hill climbing.

- Compare champion-only, top-k, novelty-aware archive, and non-recursive controls.
- Falsifier: archive consumes more budget without improving held-out robustness.

### H5 — improvement remains useful after the RSI tax

The expected reduction in future forecast loss justifies proposal, execution, evaluation,
and verification costs.

- Report dollars, wall time, sandbox-seconds, candidate count, and verification share.
- Produce an efficient frontier: held-out skill versus total cost.
- Falsifier: a static/bounded-note baseline matches the recursive system at lower total cost.

## 4. Primary-source research queue

Use primary papers, repositories, and vendor documentation. Record version/date, concrete
design claim, evidence, limitation, and its implication for this project. Do not treat a
blog summary or leaderboard screenshot as proof.

### Recursive improvement environments

- [RSI-Env](https://arxiv.org/abs/2611.01736): independent Host Controller, persistent
  research state, inherited model/harness versions, and feedback-access regimes.
- [RSIGym](https://arxiv.org/abs/2610.10310): reusable training/inference/evaluation/sandbox
  services, Data/Harness/Joint tracks, permissions, budgets, trajectories, and RSI-Index.
- [Darwin Gödel Machine](https://arxiv.org/abs/2505.22954): empirical code self-modification,
  archive-based open-ended search, parent sampling, and safety precautions.
- [The AI Scientist-v2](https://pub.sakana.ai/ai-scientist-v2/paper/paper.pdf): progressive
  agentic tree search, experiment manager, independent review, and implementation failure
  modes.

### Evaluation and cost

- [RE-Bench](https://metr.org/AI_R_D_Evaluation_Report.pdf): open-ended research engineering
  environments, long-horizon attempts, human baselines, and reproducible task scoring.
- [The RSI Tax](https://arxiv.org/abs/2611.13524): end-to-end improvement cost, verification
  overhead, unused artifacts, and comparison to simpler persistent-state baselines.

### Security and isolation

- [Benchmark-poisoning attacks on self-modifying agents](https://arxiv.org/abs/2609.17817):
  persistent contamination through poisoned evaluation tasks and implications for clean
  held-out suites.
- [Modal networking and security](https://modal.com/docs/guide/sandbox-networking): gVisor/VM
  isolation, workspace-resource boundary, outbound blocking, and allowlist limitations.
- [Modal sandbox resources](https://modal.com/docs/guide/sandbox-resources): explicit
  request/limit semantics, bursting, charging, pressure, eviction, and exit reasons.
- [Modal filesystem snapshots](https://modal.com/docs/guide/sandbox-snapshots): identical
  root-filesystem forks and snapshot lifecycle; verify what is and is not captured.

## 5. Evidence protocol

### 5.1 Pre-registration

Before running comparative experiments, freeze a machine-readable study specification:

- dataset and catalog SHA-256;
- series strata and all optimization/validation/held-out origins;
- seed list and candidate budgets;
- primary and secondary metrics;
- promotion and early-stop rules;
- treatment of missing truth, failed candidates, and zero-loss series;
- maximum Modal dollars, sandbox-seconds, and wall time;
- exact source commit, image identity, Python/dependency lock, and scorer SHA;
- analysis code and confidence-interval method.

After preregistration, changes create a new study ID rather than silently mutating a run.

### 5.2 Nested temporal evaluation

For every outer test fold:

1. candidates see only histories available at their origin;
2. inner optimization origins drive proposals;
3. inner validation origins drive promotion and early stopping;
4. outer held-out origins are revealed once after the lineage is frozen;
5. a second transfer split withholds entire source/GPU/instrument groups;
6. the official starter scorer independently checks final forecasts.

Use expanding-window and rolling-window folds. Report per-horizon and per-series-family
results, not only pooled skill. Use paired bootstrap intervals over outer folds/series and
publish all seeds, including regressions and crashes.

### 5.3 Baselines

At minimum compare:

1. flat last value;
2. official empirical and drift baselines;
3. current parameter loop;
4. equally budgeted random/grid search;
5. champion-only recursive search;
6. archive-based recursive search;
7. bounded-note/persistent-memory improvement without code changes;
8. optional bounded code-patch track.

Every baseline receives the same truth access policy and an explicit compute budget.

### 5.4 Metrics

Primary:

- outer held-out pooled pinball skill versus last value;
- mean per-series skill with uncertainty;
- q10–q90 empirical coverage and calibration error.

Robustness:

- worst-fold and worst-family skill;
- share of folds/series with positive skill;
- seed variance and performance-regression rate;
- promotion survival on the next generation and transfer split.

Efficiency:

- total and accepted-candidate sandbox-seconds;
- end-to-end dollars and wall time;
- verification/exploration/writing cost decomposition;
- skill per dollar and gap closed per 100 candidate executions;
- proportion of generated artifacts later reused.

Safety:

- attacks blocked / attempted;
- false accept and false reject rates for the promotion gate;
- typed failure coverage and time-to-termination;
- cross-candidate state or network bytes observed (expected zero).

## 6. System variants to investigate

### Track A — stronger declarative candidate language

Add composable but non-code forecasting primitives: robust level estimators, change
transforms, trend shrinkage, volatility estimators, horizon pooling, series-family pooling,
and calibration transforms. Serialize each candidate as a typed AST with a schema version.

This is the preferred first expansion because it is auditable and supports exact hashing.

### Track B — archive and research-state inheritance

Replace the single champion pointer with an append-only content-addressed archive:

- node = candidate artifact + parent hashes + proposal rationale + execution hashes;
- edges = mutation or recombination operations;
- promotion status and evaluation evidence are immutable annotations;
- failed branches remain queryable;
- parent sampling balances score, novelty, robustness, and cost.

Test whether accepted research notes help future proposals separately from code inheritance.

### Track C — bounded code patches

Only after Tracks A/B and the red-team suite pass:

- candidate may patch one isolated forecasting package with a strict file allowlist;
- no changes to orchestration, evaluator, data loader, executor, schemas, dependencies,
  network policy, resource policy, tests, or study specification;
- patch size, AST/import set, output size, and runtime are bounded;
- candidate image contains history and public development fixtures, never truth/scorer;
- host applies the patch to a clean snapshot, runs static policy checks and candidate-local
  tests, then evaluates the immutable artifact hash in a fresh sandbox;
- only the signed patch/artifact hash—not a live filesystem—may become a parent.

### Track D — Modal snapshot experiment tree

Measure whether a clean, dependency-installed base filesystem snapshot can fork equivalent
candidate environments while preserving isolation and reducing cold-start cost. Verify:

- identical base hash for siblings;
- candidate writes do not flow back to the base or across siblings;
- no volumes or secrets are captured;
- snapshot TTL and provenance are recorded;
- a no-snapshot control produces equivalent forecasts.

Treat memory snapshots as experimental and out of scope until filesystem snapshots pass.

## 7. Adversarial test matrix

Build fixtures that intentionally attempt:

| Attack | Expected outcome |
| --- | --- |
| Read a future date from input | Future row absent; request audit passes |
| Guess/read scorer implementation | No scorer/truth in image; irrelevant guesses cannot alter host score |
| Edit evaluator, study spec, or promotion rule | File absent or immutable host artifact; typed refusal |
| Change timeout/resource arguments | Candidate has no control-plane capability |
| Network/DNS exfiltration | Blocked and recorded as a sandbox failure |
| Read environment credentials | No injected secrets; secret-name/value canaries absent |
| Fork bomb / memory bomb / disk fill | Limit/timeout termination with classified exit reason |
| Huge/malformed output or duplicate keys | Schema/size refusal; never scored or promoted |
| Persist state into the next origin | Fresh sandbox and clean base hash |
| Poison a research note/benchmark | Quarantine provenance; clean-suite transfer exposes regression |
| Modify or bypass candidate-local tests | Host static policy and immutable external tests still apply |
| Replay a winning hash with different bytes | Content-address verification fails closed |

No bounded code-patch experiment begins until this suite is automated in local simulation.
Modal-specific attack tests then confirm the remote enforcement layer.

## 8. Experiment sequence and decision gates

### Phase 0 — reproduce and audit

- Re-run committed local and Modal smoke artifacts from a fresh environment.
- Compare pack gates and forecast schema against the official starter.
- Add a one-command replay/audit command and classify every existing trace.

**Gate 0:** deterministic replay, clean CI, and no provenance gaps.

### Phase 1 — research harness

- Implement preregistered split manifests, multi-seed runs, baseline adapters, paired
  statistical summaries, and the cost ledger.
- Keep the candidate grammar unchanged to isolate harness effects.

**Gate 1:** current positive result is either replicated with uncertainty or explicitly
retracted/qualified.

### Phase 2 — archive and declarative search

- Implement typed candidate ASTs and content-addressed archive nodes.
- Run champion-only versus archive versus non-recursive budget-matched controls.

**Gate 2:** archive/declarative system improves robustness or efficiency on outer folds.

### Phase 3 — security validation

- Run the full local attack corpus, then Modal attack subset.
- Add independent artifact replay and signature/hash verification.

**Gate 3:** every attack fails closed without changing a promotion decision.

### Phase 4 — bounded code patches

- Introduce the allowlisted patch builder and clean-snapshot evaluator.
- Compare against the best declarative and non-recursive controls.

**Go decision:** statistically credible transfer improvement and acceptable RSI-tax frontier
with zero unresolved boundary violations. Otherwise retain the declarative system.

## 9. Concrete deliverables

1. `docs/RESEARCH_REVIEW.md` — source matrix, claims, limitations, and design implications.
2. `studies/*.json` — immutable preregistrations and split manifests.
3. `src/rsi_sandbox/studies.py` — nested evaluation and multi-seed runner.
4. `src/rsi_sandbox/costs.py` — execution/verification cost ledger.
5. `src/rsi_sandbox/archive.py` — content-addressed lineage DAG.
6. `src/rsi_sandbox/attacks/` — adversarial candidate fixtures and expected refusals.
7. `rsi-sandbox study`, `audit`, and `red-team` commands.
8. `artifacts/study-*/` — complete results including failures and uncertainty.
9. `docs/RESEARCH_REPORT.md` — results, ablations, negative findings, and go/no-go decision.

## 10. First implementation slice for Claude Code

The first execution should not attempt all phases. It should build the foundation needed to
test the plan without weakening the existing system:

1. add immutable study-spec and deterministic split-manifest models;
2. add a cost/event ledger populated by local and Modal executors;
3. add a content-addressed archive representation for existing typed candidates;
4. add `study` or equivalent orchestration for multi-seed, multi-fold comparisons between
   flat, current recursive, and budget-matched non-recursive controls;
5. add local adversarial fixtures for future-row, malformed-output, oversized-output,
   duplicate-cell, and persistence attempts;
6. add tests, documentation, and a small synthetic study artifact that requires no event data;
7. preserve all existing CLI behavior and pass the existing real-data demo tests.

Explicitly out of scope for this slice: arbitrary code patches, new external model APIs,
live sponsor integrations, memory snapshots, large Modal studies, and claims based on a
single split.

## 11. Review questions for Claude Code

Claude should challenge this plan before implementation:

1. Which hypotheses are not identifiable under the proposed comparisons?
2. Where can selection leakage still enter across folds, research notes, or archive parents?
3. Which deliverables are premature, underspecified, or too coupled?
4. What is the smallest implementation slice that materially improves evidence quality?
5. Which acceptance tests prove the boundary rather than merely inspect configuration?
6. How should failed, timed-out, or missing forecasts enter budget-matched comparisons?
7. What would make the code-patch track a no-go even if average skill improves?

