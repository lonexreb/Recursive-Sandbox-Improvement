# Architecture and threat model

RSI separates the system into a trusted control plane and a disposable experiment plane.

The control plane owns four things candidate code must never modify: the frozen input
manifest, the future truth store, the scorer, and the promotion policy. The experiment
plane receives one origin's truncated history plus one typed candidate configuration and
returns forecasts only.

## Roles

| Role | Responsibility | Trust level |
| --- | --- | --- |
| Proposer | Mutate the champion inside a bounded parameter grammar | Trusted policy |
| Experimenter | Execute one candidate at one origin | Untrusted sandbox |
| Evaluator | Compute pinball loss, skill, coverage, and schema checks | Trusted |
| Safety critic | Enforce invariants and promotion thresholds | Trusted |

## Candidate grammar

Candidates may select a lookback, minimum sample count, recency half-life, drift
shrinkage, and interval scale. They cannot provide source code, shell arguments, imports,
or evaluator settings. This makes the improvement surface expressive enough to discover
better empirical-drift forecasts while remaining finite and auditable.

## Isolation contract

Each `(candidate, origin)` evaluation starts a fresh worker. The request contains only
series points with `date <= origin`; future truth is joined after the process exits. The
Modal backend additionally requests:

- gVisor isolation;
- `block_network=True`;
- no Modal secrets or mounted volumes;
- bounded CPU, memory, wall time, and idle time;
- a minimal Python image and a fixed worker module.

Fresh per-origin workers matter: combining several rolling origins in one process would
let candidate code inspect the later origin's history and leak it into an earlier forecast.

## Promotion and stopping

The promotion gate requires valid schemas, monotone positive quantiles, a minimum skill
gain over the incumbent, and bounded coverage regression. The loop stops after the
configured generations or when no proposal passes. Held-out scoring occurs once at the
end and cannot alter the champion.

## Known limits

The current candidate language is parameter search, not arbitrary self-editing code. That
is a deliberate safety choice and a clean base for adding signed code patches later. The
first release uses the pack's daily-statistics series; AWS spot parquet series can be
added behind the same frozen-series interface.

