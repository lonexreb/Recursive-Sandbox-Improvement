# Agent handoff

## Mission

Keep this repository a demonstrably leak-free recursive experiment system for the
Pacific GPU-price challenge. Prefer a small auditable loop over a broad agent platform.

## Invariants

1. Candidate processes receive only history dated on or before their forecast origin.
2. Truth, scoring, promotion, and resource policy remain in the trusted orchestrator.
3. Quantiles must satisfy `0 < q10 <= q50 <= q90` and the output schema is fixed.
4. Held-out origins never influence candidate proposal or promotion.
5. Modal sandboxes receive no secrets and use blocked networking plus explicit limits.
6. Every result must be reproducible from a data SHA, config SHA, seed, and git commit.

## Working commands

```bash
uv sync --extra dev --extra modal
uv run pytest
uv run ruff check .
uv run rsi-sandbox improve --pack /path/to/pack --backend local --out runs/smoke
```

Do not commit event data, `runs/`, credentials, or Modal tokens.

