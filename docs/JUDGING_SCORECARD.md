# Judging scorecard

The opening deck (page 31) assigns equal 20% weight to research rigour, novelty, results,
autonomy/self-improvement, and interpretability/reproducibility. Judging uses the live pitch,
two-minute video, and repository. Track 2 additionally emphasizes forecast performance,
economic insight, and reproducibility; Modal rewards the best use of its platform.

This is an evidence audit, not a promise. “Target” is the standard the submission package
must make obvious to a judge in three minutes.

| Criterion | Evidence now | Honest score | Remaining risk | Target |
| --- | --- | ---: | --- | ---: |
| Research rigour | Causal history truncation; truth outside sandbox; immutable evaluator; chronological embargoed splits; equal charged budgets; exact paired test; null/planted calibration; burned-set warning | 19/20 | Real recursive-vs-control effect on GPU data is not prospectively confirmed | 19/20 |
| Novelty | Sandbox is a scientific validity boundary, not just compute; recursive inheritance isolated from exploration breadth; candidate cannot alter test/resources/promotion | 19/20 | Must explain in one sentence before implementation detail | 19/20 |
| Results | 97 series, 15 origins, 4,209 cells: +0.219688 skill vs +0.183267 official drift; 4.46% lower pinball; live Modal smoke +0.4040 | 18/20 | Public development backtest; hidden score unknown | 18/20 |
| Autonomy & self-improvement | Typed proposer → sandbox experimenter → evaluator → safety gate → lineage; equal-budget recursive/fixed-anchor/flat study; promotions and rejections retained | 18/20 | Main CLI proposer is bounded deterministic search, not an LLM scientist | 18/20 |
| Interpretability & reproducibility | One-command CLI; official-format CSV; source/config/scorer/request/response/git hashes; typed failures; committed artifacts; tests; decision logs | 20/20 | Event data cannot be redistributed, so path to official pack must be supplied | 20/20 |
| **Weighted total** |  | **94/100** | A score is only useful if every claim survives live inspection | **94/100** |

## Track 2 evidence gate

| Required story | Pass condition | Evidence |
| --- | --- | --- |
| Beat a market-relevant baseline | Same cells, horizons, quantiles, truth, scorer and skill denominator | `artifacts/benchmark/report.json`; champion +0.219688 vs drift +0.183267 |
| No leakage | Candidate request contains no point after origin; held-out never drives promotion | `test_data_boundary.py`, `test_loop.py`, manifest contract |
| Calibrated uncertainty | q10 ≤ q50 ≤ q90 and coverage shown, not only point accuracy | 75.67% interval coverage on development backtest; schema gate |
| Economic insight | Translate forecast evidence into a falsifiable 2–3 year H100 buy/rent rule | `docs/GPU_VALUE_THESIS.md` |
| Reproduce in one command | Fresh checkout plus official pack yields checksummed report | README benchmark and improve commands |

## Modal challenge evidence gate

| Requirement | Evidence |
| --- | --- |
| Modal is central | Every candidate-origin can execute inside a fresh Modal Sandbox; local is a developer fallback |
| Security has scientific meaning | `block_network=True`, gVisor, no secrets/volumes; truth and evaluator never shipped |
| Resources are controlled | CPU, memory, wall-time and output caps; typed timeout/OOM/output failures |
| Remote behavior is verified | Committed live smoke: +0.4040 skill, 87.5% coverage, 24 cells |
| Auditability | Backend policy and every request/response SHA are recorded in the run manifest/trace |

## Claims a judge should be invited to challenge

1. Change any future truth row: proposals, train metrics, validation metrics, and lineage do
   not change; only sealed held-out metrics may change.
2. Give recursive and control arms unequal attempts: the study invalidates itself rather
   than rescaling the result.
3. Emit a duplicate, missing, non-positive, non-finite, or crossed quantile: the candidate
   cannot be promoted.
4. Kill a Modal sandbox or exceed its output: the failure is typed and charged; it is not a
   free search attempt.
5. Re-run the benchmark: source, catalog, contract, evaluator, git state, and result hashes
   identify exactly what was scored.

## Red lines

- Do not call the +0.219688 rolling backtest hidden, fresh, or prospective.
- Do not claim Track 1 or Track 3 as additional primary tracks.
- Do not claim Exa, past.dev, or Originator unless the live integration is actually shown.
- Do not infer a 3-year rental-price forecast from a 7-day model. The long-run thesis is a
  separate discounted-cash-flow scenario analysis.
