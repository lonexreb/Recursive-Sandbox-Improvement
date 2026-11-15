from __future__ import annotations

import argparse
from pathlib import Path

from .benchmark import run_benchmark
from .data import load_pack, load_series_file
from .executors import LocalExecutor, ModalExecutor
from .loop import date_origins, run_improvement


def _horizons(value: str) -> tuple[int, ...]:
    result = tuple(sorted({int(item) for item in value.split(",") if item.strip()}))
    if not result or any(item not in {1, 3, 7} for item in result):
        raise argparse.ArgumentTypeError("horizons must be a subset of 1,3,7")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rsi-sandbox",
        description="Bounded recursive improvement for leak-free GPU-price experiments.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    improve = subparsers.add_parser("improve", help="run the improvement loop")
    data = improve.add_mutually_exclusive_group(required=True)
    data.add_argument("--pack", help="official pack directory containing daily_statistics.csv")
    data.add_argument("--series-file", help="starter-generated series_daily.csv")
    improve.add_argument("--catalog", help="starter series_catalog.csv (with --series-file)")
    improve.add_argument("--tier", default="headline")
    improve.add_argument("--cutoff", default="2026-11-06")
    improve.add_argument("--backend", choices=("local", "modal"), default="local")
    improve.add_argument("--modal-app", default="recursive-sandbox-improvement")
    improve.add_argument("--timeout", type=int, default=60)
    improve.add_argument("--out", type=Path, required=True)
    improve.add_argument("--train-start", default="2026-09-18")
    improve.add_argument("--train-end", default="2026-10-16")
    improve.add_argument("--heldout-start", default="2026-10-23")
    improve.add_argument("--heldout-end", default="2026-10-30")
    improve.add_argument("--origin-step", type=int, default=7)
    improve.add_argument("--horizons", type=_horizons, default=(1, 3, 7))
    improve.add_argument("--generations", type=int, default=2)
    improve.add_argument("--candidates-per-generation", type=int, default=4)
    improve.add_argument("--seed", type=int, default=7)
    improve.add_argument("--min-skill-gain", type=float, default=0.002)
    improve.add_argument("--max-coverage-regression", type=float, default=0.05)
    benchmark = subparsers.add_parser(
        "benchmark", help="compare the frozen showcase champion with official drift"
    )
    benchmark.add_argument("--series-file", required=True, help="starter series_daily.csv")
    benchmark.add_argument("--catalog", required=True, help="starter series_catalog.csv")
    benchmark.add_argument("--tier", default="headline")
    benchmark.add_argument("--cutoff", default="2026-11-06")
    benchmark.add_argument("--origin-start", default="2026-07-15")
    benchmark.add_argument("--origin-end", default="2026-10-21")
    benchmark.add_argument("--origin-step", type=int, default=7)
    benchmark.add_argument("--horizons", type=_horizons, default=(1, 3, 7))
    benchmark.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "benchmark":
        dataset = load_series_file(args.series_file, args.catalog, args.cutoff, args.tier)
        origins = date_origins(args.origin_start, args.origin_end, args.origin_step)
        report = run_benchmark(dataset, origins, args.horizons, args.out)
        candidate = report["champion_metrics"]
        drift = report["official_drift_metrics"]
        comparison = report["comparison"]
        print(
            f"champion skill={candidate['skill']:.6f} vs drift={drift['skill']:.6f} | "
            f"delta={comparison['skill_delta']:+.6f} | "
            f"pinball reduction={comparison['pinball_reduction_fraction']:.2%}"
        )
        print(f"wrote {args.out}")
        return 0
    if args.series_file:
        if not args.catalog:
            raise SystemExit("--catalog is required with --series-file")
        dataset = load_series_file(args.series_file, args.catalog, args.cutoff, args.tier)
    else:
        dataset = load_pack(args.pack, args.cutoff)
    if args.backend == "modal":
        executor = ModalExecutor(args.modal_app, args.timeout)
    else:
        executor = LocalExecutor(args.timeout)
    train_origins = date_origins(args.train_start, args.train_end, args.origin_step)
    heldout_origins = date_origins(args.heldout_start, args.heldout_end, args.origin_step)
    if max(train_origins) >= min(heldout_origins):
        raise SystemExit("held-out origins must begin after the training origins")
    run_improvement(
        dataset=dataset,
        executor=executor,
        output_dir=args.out,
        train_origins=train_origins,
        heldout_origins=heldout_origins,
        cutoff=args.cutoff,
        horizons=args.horizons,
        generations=args.generations,
        candidates_per_generation=args.candidates_per_generation,
        seed=args.seed,
        min_skill_gain=args.min_skill_gain,
        max_coverage_regression=args.max_coverage_regression,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
