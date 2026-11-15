# Two-minute submission video

## Recording setup

- 1920×1080, 30 fps, cursor visible, notifications disabled.
- Terminal font at least 22 px. Keep the repository, terminal, and five-slide pitch deck open.
- Pre-run the benchmark once to warm the environment. Keep `artifacts/modal-smoke/run.json`
  and `trace.jsonl` open as the verified fallback if the live Modal service is slow.
- Display Track 2 as the primary track and Modal as the sponsor challenge.

## Shot list and narration

| Time | Screen | Narration |
| --- | --- | --- |
| 0:00–0:10 | Pitch slide 1 | “Self-improving systems can manufacture progress if candidates control their own test. RSI freezes truth, the scorer, resources, and promotion outside the candidate sandbox.” |
| 0:10–0:27 | Pitch slide 2, then `artifacts/benchmark/report.json` | “On 97 official series and 4,209 matched cells, our frozen champion scores plus 0.2197 skill versus plus 0.1833 for official drift. It wins 12 of 15 weekly origins and lowers pinball loss 4.46 percent.” |
| 0:27–0:35 | Highlight `paired_inference` | “The 90 percent interval crosses zero, so we call this promising development evidence, not a conclusive hidden-test result.” |
| 0:35–0:55 | Pitch slide 3 | “Each candidate-origin evaluation gets causal history only. Modal starts a fresh gVisor sandbox with blocked outbound network, no secrets or volumes, and fixed resource limits. Only the trusted evaluator sees truth.” |
| 0:55–1:18 | Terminal: start the live command, then show a trace | “The scientist proposes bounded mutations, executes them, records request and response hashes, rejects failures, and promotes only candidates that improve skill without unacceptable coverage loss.” |
| 1:18–1:38 | Pitch slide 4 | “Recursive and fixed-anchor controls receive the same operator, random streams, seen set, and charged attempts. Only inheritance differs. On seven preregistered real-data folds, recursion gains 2.63 skill points over control; six folds favor recursion. The exact p-value is 0.09375, so this corroborates rather than concludes.” |
| 1:38–1:55 | Pitch slide 5 | “At the pack’s 33.6-thousand-dollar H100 reference cost, our base three-year value is 25.1 thousand. Rent at reference price. Buy near 25 thousand or with defensible utilization above 80 percent.” |
| 1:55–2:00 | Repository URL | “The model may change the method. It never changes the test.” |

## Commands visible on screen

Headline comparison:

```bash
uv run rsi-sandbox benchmark \
  --series-file "$SERIES_DAILY" \
  --catalog "$SERIES_CATALOG" \
  --out runs/video-benchmark.json
```

Live Modal loop:

```bash
uv run rsi-sandbox improve \
  --series-file "$SERIES_DAILY" \
  --catalog "$SERIES_CATALOG" \
  --backend modal \
  --horizons 1 \
  --generations 1 \
  --candidates-per-generation 2 \
  --out runs/video-modal
```

Trace inspection:

```bash
jq '{data, executor_policy, champion, train_metrics, heldout_metrics, ledger}' \
  runs/video-modal/run.json
head -n 3 runs/video-modal/trace.jsonl | jq
```

Preregistered causal result:

```bash
jq '{spec_sha256, provenance, analysis}' \
  artifacts/study/gpu_recursive_vs_control_v2.json
```

## Fallback if the live service is slow

Do not hide or edit a failure. Say: “The live service did not return inside the demo window,
so I am switching to the committed verified run.” Open `artifacts/modal-smoke/run.json` and
`trace.jsonl`, show `runtime: gvisor`, `block_network: true`, the request/response hashes,
and the +0.4040 smoke holdout skill. The fallback proves a prior run, not current availability.

## Claims to keep verbatim

- “Public development evidence,” not “hidden,” “fresh,” or “state of the art.”
- “Corroborating preregistered real-data evidence,” not “conclusive recursive improvement.”
- “Track 2 primary, Modal challenge,” not three simultaneous primary tracks.
- “Base-case scenario,” not “three-year forecast.”
