"""Shared structural and path-safety checks for companion inputs."""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from pathlib import Path

from messy_orders.rules import SOURCE_FIELDS


def validate_orders_csv_structure(path: Path) -> None:
    """Enforce the shared header/width policy before either loader reads data."""

    expected_field_count = len(SOURCE_FIELDS)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration as error:
            raise ValueError("orders CSV is empty") from error

        actual_headers = tuple(header)
        missing_headers = [field for field in SOURCE_FIELDS if field not in header]
        if missing_headers:
            raise ValueError(f"orders CSV missing headers: {', '.join(missing_headers)}")
        unexpected_headers = [field for field in header if field not in SOURCE_FIELDS]
        if unexpected_headers:
            raise ValueError(
                "orders CSV has unexpected headers: " + ", ".join(unexpected_headers)
            )
        if actual_headers != SOURCE_FIELDS:
            raise ValueError(
                "orders CSV headers are out of order; expected: "
                + ", ".join(SOURCE_FIELDS)
            )

        logical_record = 1
        for row in reader:
            # csv.DictReader and pandas both ignore physically blank lines. Keep
            # that behavior explicit here so the two implementations agree.
            if row == []:
                continue
            logical_record += 1
            if len(row) != expected_field_count:
                raise ValueError(
                    f"orders CSV row {logical_record} has {len(row)} fields; "
                    f"expected {expected_field_count}"
                )


def plan_safe_io_paths(
    inputs: Mapping[str, Path],
    output_dir: Path,
    output_names: Sequence[str],
) -> tuple[dict[str, Path], Path, dict[str, Path]]:
    """Resolve all paths and reject input/output aliases before any write."""

    resolved_inputs = {
        label: path.expanduser().resolve() for label, path in inputs.items()
    }
    resolved_output_dir = output_dir.expanduser().resolve()
    resolved_outputs = {
        name: (resolved_output_dir / name).resolve() for name in output_names
    }

    collisions = [
        (input_label, output_name, input_path)
        for input_label, input_path in resolved_inputs.items()
        for output_name, output_path in resolved_outputs.items()
        if input_path == output_path
    ]
    if collisions:
        details = "; ".join(
            f"{input_label} collides with {output_name}: {path}"
            for input_label, output_name, path in collisions
        )
        raise ValueError(f"input/output path collision: {details}")

    return resolved_inputs, resolved_output_dir, resolved_outputs
