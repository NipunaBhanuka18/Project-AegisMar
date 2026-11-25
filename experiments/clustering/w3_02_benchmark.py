"""W3-02 benchmark runner: BallTree reference vs. H3 candidate acceleration.

Example (full locked protocol):

    uv run python experiments/clustering/w3_02_benchmark.py \
        -i data/processed/lalb_20250101_v1_1/cleaned_ais.parquet \
        -o experiments/outputs/w3_02_benchmark_results.json

See ``docs/03-research/w3-02-benchmark-protocol.md`` for the locked protocol.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from aegismar.clustering.benchmark import (
    DEFAULT_SCALES,
    W302BenchmarkConfig,
    run_w3_02_benchmark,
)

DEFAULT_OUTPUT = Path("experiments/outputs/w3_02_benchmark_results.json")
EXIT_OK = 0
EXIT_USAGE_ERROR = 1
EXIT_CHECKS_FAILED = 2


def _parse_scale(value: str) -> int | None:
    if value.lower() == "full":
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"scale must be a positive integer or 'full', got {value!r}"
        ) from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError(f"scale must be >= 1, got {parsed}")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    """Build the W3-02 runner argument parser."""
    parser = argparse.ArgumentParser(
        prog="w3_02_benchmark",
        description="W3-02 BallTree vs. H3 ST-DBSCAN benchmark (correctness, timing, memory).",
    )
    parser.add_argument(
        "--input", "-i", required=True, help="Canonical cleaned AIS Parquet dataset"
    )
    parser.add_argument(
        "--output",
        "-o",
        default=str(DEFAULT_OUTPUT),
        help=f"Result JSON path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--scales",
        nargs="+",
        type=_parse_scale,
        default=None,
        help="Override scale tiers, ascending, 'full' last (default: 10000 50000 100000 full)",
    )
    parser.add_argument("--trials", type=int, default=10, help="Measured trials (default: 10)")
    parser.add_argument("--warmup", type=int, default=1, help="Warm-up runs (default: 1)")
    parser.add_argument(
        "--oracle-rows", type=int, default=2000, help="Oracle prefix rows (default: 2000)"
    )
    parser.add_argument(
        "--sensitivity-resolutions",
        nargs="+",
        type=int,
        default=[7, 9],
        help="H3 sensitivity resolutions (default: 7 9)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Allow replacing an existing output JSON",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the benchmark and write the JSON record. Returns a process exit code."""
    args = build_parser().parse_args(argv)
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.is_file():
        print(f"Error: input dataset not found: {input_path}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    if output_path.exists() and not args.overwrite:
        print(
            f"Error: output already exists: {output_path}. Pass --overwrite to replace it.",
            file=sys.stderr,
        )
        return EXIT_USAGE_ERROR

    try:
        config = W302BenchmarkConfig(
            dataset_path=input_path,
            scales=tuple(args.scales) if args.scales is not None else DEFAULT_SCALES,
            measured_trials=args.trials,
            warmup_runs=args.warmup,
            oracle_max_rows=args.oracle_rows,
            sensitivity_h3_resolutions=tuple(args.sensitivity_resolutions),
        )
    except ValueError as exc:
        print(f"Error: invalid benchmark configuration: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    results = run_w3_02_benchmark(config, log=lambda msg: print(msg, flush=True))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Results written to {output_path}")

    if results["status"] != "completed":
        print(f"WARNING: benchmark status is {results['status']!r}", file=sys.stderr)
        return EXIT_CHECKS_FAILED
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
