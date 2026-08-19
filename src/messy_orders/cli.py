"""Command-line interface for the Messy Orders Cleanup companion."""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Sequence
from pathlib import Path

from messy_orders.pipeline import run_pipeline

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clean-orders")
    subparsers = parser.add_subparsers(dest="command", required=True)

    clean_parser = subparsers.add_parser("clean", help="clean synthetic order data")
    clean_parser.add_argument("--orders", type=Path, required=True)
    clean_parser.add_argument("--customers", type=Path, required=True)
    clean_parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "clean":
        try:
            report = run_pipeline(args.orders, args.customers, args.output_dir)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            LOGGER.error("cleanup failed: %s", exc)
            return 1
        LOGGER.info(
            "cleanup complete: input=%s accepted=%s rejected=%s",
            report["input_rows"],
            report["accepted_rows"],
            report["rejected_rows"],
        )
        return 0

    parser.error(f"unsupported command: {args.command}")
    return 2
