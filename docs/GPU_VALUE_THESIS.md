# Is an H100 worth buying for the next 2–3 years?

## Decision

**Base case: rent, do not buy at the $33,600 reference capex.** Buy only when delivered
per-GPU cost is approximately **$25,000 or lower**, or when a workload owner can defend
utilization above 80% with revenue or avoided rental spend that is not already captured in
the base case.

This is a decision model, not a claim that the 1/3/7-day forecaster predicts prices three
years out. Short-horizon forecasts inform current rental-rate and uncertainty inputs; the
long horizon is handled by explicit scenarios.

## Anchors from the event pack

- `hardware_fundamentals.csv` lists NVIDIA H100 SXM5 80GB reference release price at
  **$33,600 per GPU** (derived from an eight-GPU DGX sale reference; the pack notes the
  uncertainty and alternative bill-of-materials estimate).
- On the pack cutoff, 2026-11-06, listed H100 rates vary radically by venue and contract.
  The starter-built series include roughly $1.80/hour at the cheapest aggregator, around
  $2.25–$3.33/hour in marketplace asks, and about $3.55–$4.19/hour in selected neocloud
  on-demand rate cards. These are different instruments, not one fungible market price.
- The forecasting result is therefore evaluated across the official 97-series scope rather
  than cherry-picking one H100 quote.

## Three-year discounted cash-flow model

For year `y`:

```text
cash_y = 8,760 × utilization × (rental_rate_y − variable_opex) − fixed_opex
rental_rate_y = initial_rate × (1 − annual_rate_decline)^(y−1)
max purchase price = Σ cash_y / 1.12^y + terminal_value / 1.12^3
```

The 12% discount rate represents hardware, counterparty, utilization, and obsolescence risk.
Power is included in variable opex; networking, host amortization, failures, and operations
must also fit within that input. Taxes and financing are excluded.

| Scenario | Utilization | Initial realized rate | Annual rate decline | Variable + fixed opex | Year-3 terminal | Max purchase price | NPV at $33.6k |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Bear | 45% | $1.75/h | 35% | $0.45/h + $1,200/y | $3,000 | $6,801 | −$26,799 |
| Base | 65% | $2.50/h | 22% | $0.40/h + $900/y | $7,000 | **$25,076** | **−$8,524** |
| Bull | 82% | $3.25/h | 10% | $0.35/h + $700/y | $12,000 | $51,875 | +$18,275 |

## What would change the answer?

Buy becomes rational when at least one of these is evidenced:

1. delivered capex falls below the scenario's max purchase price;
2. committed internal demand keeps utilization above 80%;
3. the alternative is a high on-demand rate, so avoided rental spend exceeds realized
   third-party rental revenue;
4. networking/topology makes owned H100s materially more productive than rented cards;
5. resale or redeployment value is contractually credible rather than assumed.

The answer moves toward rent when newer accelerators compress H100 rates, workload demand is
bursty, cluster reliability is costly, or low marketplace quotes are actually available at
the required topology and duration.

## Falsification and update policy

- Recompute the table when the champion's current q10/q50/q90 range moves the defensible
  initial realized rate outside the selected scenario.
- Record utilization from actual jobs, not reservation plans.
- Treat venue series separately; never splice spot, serverless, marketplace ask, and
  hyperscaler list prices into a synthetic history.
- Publish the assumptions beside the answer. A judge can replace any input and see exactly
  where “buy” flips to “rent.”
