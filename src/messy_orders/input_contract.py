"""Shared structural and path-safety checks for companion inputs."""

from __future__ import annotations

import csv
import io
import json
import os
from collections.abc import Mapping, Sequence
from itertools import combinations
from pathlib import Path

from messy_orders.rules import SOURCE_FIELDS


def load_orders_csv_records(path: Path) -> list[dict[str, object]]:
    """Parse one strict CSV representation shared by both workflows."""

    expected_field_count = len(SOURCE_FIELDS)
    with path.open("r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    if "\x00" in text:
        raise ValueError("orders CSV contains an embedded NUL character")

    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
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

        records: list[dict[str, object]] = []
        logical_record = 1
        for row in reader:
            # A physically blank line is not a logical CSV record.
            if row == []:
                continue
            logical_record += 1
            if len(row) != expected_field_count:
                raise ValueError(
                    f"orders CSV row {logical_record} has {len(row)} fields; "
                    f"expected {expected_field_count}"
                )
            record: dict[str, object] = dict(zip(SOURCE_FIELDS, row, strict=True))
            record["source_row"] = logical_record
            records.append(record)
    except csv.Error as error:
        raise ValueError(f"orders CSV is malformed: {error}") from error
    return records


def validate_orders_csv_structure(path: Path) -> None:
    """Compatibility wrapper that applies the complete shared CSV contract."""

    load_orders_csv_records(path)


def load_strict_json(path: Path) -> object:
    """Decode JSON while rejecting duplicate member names at every depth."""

    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for name, value in pairs:
            if name in result:
                raise ValueError(f"customers JSON has duplicate member name: {name}")
            result[name] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


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
    resolved_outputs: dict[str, Path] = {}
    for name in output_names:
        name_path = Path(name)
        if (
            name_path.is_absolute()
            or name_path.name != name
            or name in {"", ".", ".."}
        ):
            raise ValueError(f"output name must be one file name: {name}")
        declared_path = resolved_output_dir / name
        if declared_path.is_symlink():
            raise ValueError(f"output path must not be a symbolic link: {declared_path}")
        resolved_target = declared_path.resolve()
        if not resolved_target.is_relative_to(resolved_output_dir):
            raise ValueError(f"output path escapes output directory: {declared_path}")
        resolved_outputs[name] = declared_path

    collisions = [
        (input_label, output_name, input_path)
        for input_label, input_path in resolved_inputs.items()
        for output_name, output_path in resolved_outputs.items()
        if input_path == output_path
        or (
            input_path.exists()
            and output_path.exists()
            and os.path.samefile(input_path, output_path)
        )
    ]
    if collisions:
        details = "; ".join(
            f"{input_label} collides with {output_name}: {path}"
            for input_label, output_name, path in collisions
        )
        raise ValueError(f"input/output path collision: {details}")

    output_collisions = [
        (left_name, right_name, left_path)
        for (left_name, left_path), (right_name, right_path) in combinations(
            resolved_outputs.items(), 2
        )
        if left_path == right_path
        or (
            left_path.exists()
            and right_path.exists()
            and os.path.samefile(left_path, right_path)
        )
    ]
    if output_collisions:
        details = "; ".join(
            f"{left_name} collides with {right_name}: {path}"
            for left_name, right_name, path in output_collisions
        )
        raise ValueError(f"output/output path collision: {details}")

    linked_outputs = [
        (name, path)
        for name, path in resolved_outputs.items()
        if path.exists() and path.stat().st_nlink > 1
    ]
    if linked_outputs:
        details = "; ".join(f"{name}: {path}" for name, path in linked_outputs)
        raise ValueError(f"output path must not be a hard link: {details}")

    return resolved_inputs, resolved_output_dir, resolved_outputs
