# Recursive Sandbox Improvement

`Recursive-Sandbox-Improvement` (RSI) is a small AI-scientist loop that improves a
GPU-price quantile forecaster without letting candidate code touch the evaluator,
future truth, credentials, or the network.

**Submission strategy:** Track 2 (Pacific GPU Value) is the one primary track; Modal is the
sponsor challenge. The system borrows AI-scientist and typed-role ideas from Tracks 1 and 3,
but does not claim those additional primary tracks.

- **Track 2 result:** forecast q10/q50/q90 GPU prices at 1, 3, and 7 days.
- **Recursive method:** propose, run, score, critique, and retain candidate methods.
- **Typed roles:** proposer, experimenter, evaluator, and safety gate exchange hashed artifacts.
- **Modal challenge:** every candidate/origin can run in a fresh gVisor sandbox with blocked
  networking, no secrets, bounded CPU/RAM/time, and history truncated at the origin.

The core claim is intentionally narrow: this is **bounded recursive improvement of a
forecasting policy**, not an autonomous system rewriting its own controls. Candidate
parameters may change; the orchestrator, sandbox policy, evaluator, and promotion gate may not.

## Quick start

```bash
uv sync --extra dev --extra modal

# Fast local proof on the official Pacific GPU-price pack.
uv run rsi-sandbox improve \
  --pack /path/to/gpu-price-pack-v0.1.1-handover \
  --backend local \
  --out runs/local-demo

# Run the same isolated candidate contract on Modal.
uv run modal setup
uv run rsi-sandbox improve \
  --pack /path/to/gpu-price-pack-v0.1.1-handover \
  --backend modal \
  --generations 1 \
  --candidates-per-generation 2 \
  --out runs/modal-demo
```

The output directory contains a checksummed run manifest, every proposal and score,
the champion lineage, a held-out report, and a cutoff forecast CSV compatible with the
official starter scorer.

### Reproduce the headline comparison

After running the event starter's `build_series.py`, compare the frozen showcase champion
with the starter's empirical-drift baseline on the identical 97-series, 15-origin, 1/3/7-day
scope:

```bash
uv run rsi-sandbox benchmark \
  --series-file /path/to/series_daily.csv \
  --catalog /path/to/series_catalog.csv \
  --out runs/official-backtest.json
```

The committed result is in [artifacts/benchmark/report.json](artifacts/benchmark/report.json):
**+0.219688 skill** versus **+0.183267** for official drift, a +0.036421 skill delta and
4.46% lower pinball loss. Both methods score the same 4,209 cells; the champion wins 12 of
15 weekly origins. The 90% origin-block bootstrap interval for the pinball delta includes
zero, so this is promising public development evidence—not a statistically conclusive,
hidden-test, or prospective result—and the artifact says so.

## Verified results

The committed [full demo](artifacts/demo/run.json) uses 37 official headline series,
five optimization origins, and two untouched held-out origins. The loop promoted twice:

| Run | Train skill | Held-out skill | Held-out coverage | Cells |
| --- | ---: | ---: | ---: | ---: |
| Local full loop (1/3/7 day) | +0.1892 | **+0.0513** | 72.4% | 196 |
| Modal smoke (1 day) | +0.3454 | **+0.4040** | 87.5% | 24 |

Skill is `1 - candidate pinball / last-value pinball`; positive is better. The Modal
smoke artifact is in [artifacts/modal-smoke/run.json](artifacts/modal-smoke/run.json).
These results are evidence for the implementation, not a claim about withheld judging data.

> **Development / burned evidence.** The +0.0513 held-out figure was published and has been
> inspected, so those origins can no longer serve as a fresh confirmation set. Treat it as
> development evidence only; any new real-data claim needs a fresh, pre-committed block and
> its study hash.

## Budget-matched study (research harness)

`rsi-sandbox study` asks whether
champion-conditioned search beats a matched champion-independent control at an equal
budget, using preregistered, embargoed folds.

```bash
uv run rsi-sandbox study \
  --series-file /path/to/series_daily.csv \
  --catalog /path/to/series_catalog.csv \
  --spec studies/gpu_recursive_vs_control_v1.json \
  --out runs/gpu-recursive-vs-control-v1.json
```

- Arms: `flat` (no search, re-run to match the ledger), `recursive` (local mutations of
  the evolving champion, fixed seeds skipped) and `control` (the identical mutation
  operator, rng stream, `seen` set and budget, anchored on the fixed starting incumbent).
  Until a promotion changes the champion the two arms draw identical proposals, so the
  gap isolates inheritance rather than exploration breadth.
- Primary budget: charged candidate-origin execution attempts. A failed candidate is
  charged its full slot; infrastructure failures retry at most once and are counted
  separately. Unequal budgets invalidate the comparison. No Modal dollars are measured.
- Train origins screen, validation origins promote, held-out origins run once per arm after
  the lineage is frozen. Splits must be disjoint, chronological and separated by at least
  `max(horizons)` days; study specs reject unknown keys and resource-policy keys.
- Output: a canonical result dict (spec SHA, scorer SHA, git commit and dirty-tree hash,
  per-run trace hash over request/response SHA-256, sealed held-out ledger, and a paired
  fold difference with an exact sign-flip permutation test, at most 14 folds).
- Synthetic calibration (not evidence about GPU prices). `planted`: a steady trend makes
  `drift_scale` and `interval_scale` individually beneficial, so the recursive arm can stack
  them across generations while the control plateaus — it tests compounding through
  inheritance and nothing else. `null`: unpredictable shocks; over 20 studies the mean
  recursive-minus-control gap is -0.004 skill (SE 0.010) with 0/20 false positives.

## Safety boundary

```text
trusted orchestrator                untrusted candidate sandbox
--------------------                ---------------------------
frozen data manifest  --history-->  deterministic worker
truth store                         candidate parameters only
pinball evaluator      <--forecast-- no truth / network / secrets
promotion gate                      CPU, RAM and wall-time limits
```

A candidate is promoted only when it beats the incumbent on optimization origins,
preserves monotone quantiles, emits the exact schema, stays within its budget, and does
not regress interval coverage beyond the configured tolerance. Held-out origins are
reported once after the loop and never drive selection.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the threat model and
[docs/HACKATHON.md](docs/HACKATHON.md) for the submission/demo map,
[docs/JUDGING_SCORECARD.md](docs/JUDGING_SCORECARD.md) for the evidence audit, and
[docs/GPU_VALUE_THESIS.md](docs/GPU_VALUE_THESIS.md) for the 2–3 year H100 decision.

## Pitch package

- [Three-minute judging deck](pitch/RSI_Hackathon_Pitch_v2.pptx), with editable native
  charts, source notes, and a validated five-slide structure.
- [Two-minute video shot list](docs/VIDEO_SHOTLIST.md), including exact screen actions,
  narration, claim boundaries, and a live-service fallback.
- [Spoken finals script](docs/HACKATHON.md#three-minute-finals-script).

## Data

The repository does not redistribute the event data. Point `--pack` at the official
directory containing `daily_statistics.csv`. RSI applies the pack's cutoff and headline
gates and records the source file SHA-256 in every run.

If you already ran the official starter's `build_series.py`, use its exact scope instead:

```bash
uv run rsi-sandbox improve \
  --series-file /path/to/series_daily.csv \
  --catalog /path/to/series_catalog.csv \
  --tier headline \
  --backend local \
  --out runs/starter-scope
```

## License

MIT. Event data retains its own source licenses and is never copied into this repository.
