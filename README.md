# Recursive Sandbox Improvement

`Recursive-Sandbox-Improvement` (RSI) is a small AI-scientist loop that improves a
GPU-price quantile forecaster without letting candidate code touch the evaluator,
future truth, credentials, or the network.

It combines the hackathon tracks into one demo:

- **Track 1 — AI scientist:** propose, run, score, critique, and retain candidate methods.
- **Track 2 — GPU value:** forecast q10/q50/q90 GPU prices at 1, 3, and 7 days.
- **Track 3 — multi-agent systems:** explicit proposer, experimenter, evaluator, and safety-gate roles.
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
[docs/HACKATHON.md](docs/HACKATHON.md) for the submission/demo map.

## Data

The repository does not redistribute the event data. Point `--pack` at the official
directory containing `daily_statistics.csv`. RSI applies the pack's cutoff and headline
gates and records the source file SHA-256 in every run.

## License

MIT. Event data retains its own source licenses and is never copied into this repository.

