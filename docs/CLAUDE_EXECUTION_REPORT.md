# Claude Code execution report

Branch: `claude/deep-research-execution`

## Outcome

Claude Code implemented the bounded research-harness slice from
`CLAUDE_EXECUTION_HANDOFF.md`. Its first pass was rejected because it exceeded the production
line cap and used an unfair global-search control that produced a systematic null advantage.
A corrective Claude pass replaced that control with a matched local proposer and reduced the
production diff below the cap. Codex then reviewed the diff, added one fail-fast overflow
regression, and independently reran local and live Modal verification.

## Implemented

- immutable, hashed train/validation/held-out split contracts with chronology and embargo;
- exact candidate-origin attempt accounting across flat, recursive, and matched-control arms;
- champion-conditioned and fixed-anchor proposal modes using the same mutation operator;
- typed executor failures, response hashes, exit-status checks, and bounded output handling;
- preservation of held-out results when cutoff forecasting fails;
- git/scorer/config provenance in run records;
- deterministic planted and pure-null synthetic study fixtures;
- a programmatic, sealed-heldout study API with an exact paired sign-flip test;
- regression tests for leakage, ordering, budgets, failure taxonomy, Modal policy, calibration,
  and backward compatibility.

The study CLI, arbitrary code patches, archives, snapshots, and real-data research claims were
deferred. `evaluation.py`, `data.py`, `Dataset.history_request`, and `cli.py` are unchanged.

## Scientific calibration

These are synthetic harness checks, not GPU-price results:

- Pure null: mean recursive-minus-control skill **−0.0042**, standard error 0.0103,
  and **0/20** false positives at `p < 0.05`.
- Planted compounding task across three data seeds: gaps **+0.044, +0.067, +0.046**;
  exact paired-test p-values 0.0078, 0.0156, and 0.0156.

The planted fixture tests one narrow causal property: an inherited champion can stack two
individually useful local changes, while the matched fixed-anchor control cannot. It does not
establish improvement on GPU pricing or open-ended RSI.

## Independent verification

- Production diff: **495 net lines** relative to the reviewed-plan commit (limit: 500).
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: passed.
- `uv run pytest`: **68 passed**.
- `git diff --check`: passed.
- Full local GPU-pack regression: same champion, lineage, metrics, and byte-identical
  `forecast_2026-11-06.csv`; held-out skill remains +0.0513 and is labeled burned/development
  evidence.
- Live Modal regression: fresh gVisor sandboxes, blocked network, no secrets/volumes,
  +0.4040 one-horizon smoke holdout skill.

## Remaining gates

Before any new real-data claim, pre-commit a fresh confirmation block and study hash. Run enough
non-overlapping folds to assess recursive-minus-control uncertainty. If that interval includes
zero, H1 remains unsupported and archive/code-patch work stays deferred.

