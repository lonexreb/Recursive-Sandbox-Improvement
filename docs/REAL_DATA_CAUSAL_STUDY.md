# Real-data recursive-versus-control study

## Question

Does inheriting a promoted champion improve held-out GPU-price forecast skill relative to
the identical mutation operator, random streams, seen set, and budget anchored on the fixed
starting method?

This study isolates inheritance. It does not compare unrestricted agent architectures or
claim open-ended recursive self-improvement.

## Preregistration trail

- V1 was committed at `05b50e09e89dd91b59bd4dd9bc124eca4ff29eba` before execution.
  It failed because public headline data have a March–April truth gap. No V1 result was
  generated. The specification and failure record remain committed.
- V2 was committed at `7bf60d73888e26cf96abb81c44ffa152bf14d3a1` before execution.
  Its spec SHA-256 is
  `fb16adc64c6b611546b5cfeb520c79df00961d3d4ecf1c2bde3b499ade7da525`.
- The V2 result records that exact commit with `git_dirty: false`. Its result SHA-256 is
  `6a928e34336ed22ac79257b006bb95b966220b8e642f41c982958c00462e0d20`.

V2 uses seven chronological, non-overlapping held-out origin blocks from June through
October, two fixed search seeds, 1/3/7-day horizons, and a seven-day embargo between train,
validation, and held-out phases. Each arm receives 14 charged optimization executions per
fold and seed. Across the study that is 588 equal-budget charged executions plus 42 sealed
held-out executions.

## Result

| Arm | Mean held-out skill over fold/seed runs | Positive runs |
| --- | ---: | ---: |
| Flat last value | 0.0000 | 0/14 |
| Fixed-anchor control | +0.1435 | 11/14 |
| Recursive inheritance | **+0.1698** | **12/14** |

The preregistered primary contrast is recursive minus control, averaged by fold after
pairing the two seeds:

- mean gap: **+0.02633 skill**;
- positive fold means: **6/7**;
- exact two-sided paired sign-flip p-value: **0.09375**;
- held-out scope per arm/seed: **1,959 forecast cells** across seven origins.

The result is directionally consistent with inherited improvements compounding, but the
two-sided test does not cross 0.05. It is corroborating real-data evidence, not a conclusive
confirmation. The public data and outcome are now burned development evidence; a future
claim needs new forward data or a genuinely hidden evaluation.

## Reproduce

```bash
uv run rsi-sandbox study \
  --series-file /path/to/series_daily.csv \
  --catalog /path/to/series_catalog.csv \
  --spec studies/gpu_recursive_vs_control_v2.json \
  --out runs/gpu-recursive-vs-control-v2.json
```

Inspect `artifacts/study/gpu_recursive_vs_control_v2.json` for every arm/fold/seed lineage,
attempt ledger, trace hash, held-out metric, exact fold contrast, data hash, scorer hash,
spec hash, and clean Git provenance.
