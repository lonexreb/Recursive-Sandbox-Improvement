# Hackathon submission map

## One-line pitch

An AI scientist that recursively improves GPU-price forecasts while every experiment runs
inside a fresh, credential-free Modal sandbox that cannot see future truth.

## Two-minute demo

1. Show the immutable boundary and the data SHA in `run.json`.
2. Start `rsi-sandbox improve` and show candidates branching from the incumbent.
3. Open a candidate trace: truncated history in, forecasts out, no truth or network.
4. Show rejected variants alongside the promoted lineage.
5. Reveal the held-out skill/coverage report and the official-format forecast CSV.

## Track mapping

- Track 1: the proposer/experimenter/evaluator/critic loop is the AI scientist.
- Track 2: the objective is quantile GPU-price forecast skill over 1/3/7-day horizons.
- Track 3: the roles exchange typed artifacts instead of an unstructured group chat.
- Modal: isolation is part of scientific validity, not merely compute hosting.

## Sponsor integration seams

- **Exa:** write a dated evidence bundle before the run; hash it into the manifest; never
  let live search enter a scoring sandbox.
- **past.dev:** publish typed proposal, critique, and result events to the shared timeline.
- **Originator:** attach the run/config/data hashes and champion parent to every trace.

These seams are outside the scoring boundary so a missing sponsor service cannot make the
benchmark irreproducible.

## Judging claim

The strongest claim is not “we solved recursive self-improvement.” It is: “we built a
repeatable protocol where improvement can happen without candidates controlling their
own test, resources, credentials, or promotion.”

