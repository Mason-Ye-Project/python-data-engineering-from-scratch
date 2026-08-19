"""Pandas-backed canonical data-cleaning workflow."""

from __future__ import annotations

import hashlib
import json
import platform
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from messy_orders.input_contract import plan_safe_io_paths, validate_orders_csv_structure
from messy_orders.rules import (
    CLEAN_FIELDS,
    REJECT_FIELDS,
    SOURCE_FIELDS,
    source_rejection,
    validate_and_clean_order,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_customers(path: Path) -> dict[str, dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("customers JSON must contain an array")

    customers: dict[str, dict[str, str]] = {}
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("each customer must be a JSON object")
        customer_id = item.get("customer_id")
        customer_name = item.get("customer_name")
        contact = item.get("contact")
        if not isinstance(customer_id, str) or not customer_id:
            raise ValueError("each customer requires customer_id text")
        if not isinstance(customer_name, str) or not customer_name:
            raise ValueError(f"customer {customer_id} requires customer_name text")
        if not isinstance(contact, dict) or not isinstance(contact.get("city"), str):
            raise ValueError(f"customer {customer_id} requires contact.city text")
        if customer_id in customers:
            raise ValueError(f"duplicate customer_id: {customer_id}")
        customers[customer_id] = {
            "customer_name": customer_name,
            "customer_city": contact["city"],
        }
    return customers


def load_orders(path: Path) -> list[dict[str, object]]:
    validate_orders_csv_structure(path)

    frame = pd.read_csv(path, dtype=str, keep_default_na=False)

    records: list[dict[str, object]] = []
    for index, row in frame.iterrows():
        record = {field: row[field] for field in SOURCE_FIELDS}
        # This is a logical CSV-record ordinal. The header occupies position 1.
        record["source_row"] = int(index) + 2
        records.append(record)
    return records


def clean_orders(
    orders: Iterable[dict[str, object]],
    customers: dict[str, dict[str, str]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    order_rows = list(orders)
    source_by_row = {int(row["source_row"]): row for row in order_rows}
    valid_candidates: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []

    for source in order_rows:
        clean_row, reasons = validate_and_clean_order(source, customers)
        if clean_row is None:
            rejected.append(source_rejection(source, reasons))
        else:
            valid_candidates.append(clean_row)

    last_row_for_order = {
        str(row["order_id"]): int(row["source_row"]) for row in valid_candidates
    }

    accepted: list[dict[str, object]] = []
    for clean_row in valid_candidates:
        order_id = str(clean_row["order_id"])
        if int(clean_row["source_row"]) != last_row_for_order[order_id]:
            rejected.append(
                source_rejection(
                    source_by_row[int(clean_row["source_row"])],
                    ["duplicate_order_id_superseded"],
                )
            )
        else:
            accepted.append(clean_row)

    accepted.sort(key=lambda row: int(row["source_row"]))
    rejected.sort(key=lambda row: int(row["source_row"]))
    return accepted, rejected


def write_csv(
    rows: list[dict[str, object]], fields: tuple[str, ...], path: Path
) -> None:
    frame = pd.DataFrame(rows, columns=fields)
    frame.to_csv(path, index=False, lineterminator="\n")


def write_json(payload: object, path: Path) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run_pipeline(
    orders_path: Path, customers_path: Path, output_dir: Path
) -> dict[str, object]:
    inputs, output_dir, outputs = plan_safe_io_paths(
        {"orders": orders_path, "customers": customers_path},
        output_dir,
        (
            "orders_clean.csv",
            "orders_rejected.csv",
            "quality_report.json",
            "run_manifest.json",
        ),
    )
    orders_path = inputs["orders"]
    customers_path = inputs["customers"]
    input_hashes = {
        "customers.json": sha256_file(customers_path),
        "orders.csv": sha256_file(orders_path),
    }

    customers = load_customers(customers_path)
    orders = load_orders(orders_path)
    accepted, rejected = clean_orders(orders, customers)

    clean_path = outputs["orders_clean.csv"]
    rejected_path = outputs["orders_rejected.csv"]
    report_path = outputs["quality_report.json"]
    manifest_path = outputs["run_manifest.json"]

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(accepted, CLEAN_FIELDS, clean_path)
    write_csv(rejected, REJECT_FIELDS, rejected_path)

    reason_counts: Counter[str] = Counter()
    for row in rejected:
        reason_counts.update(str(row["reason_codes"]).split("|"))

    report: dict[str, object] = {
        "accepted_rows": len(accepted),
        "input_rows": len(orders),
        "reason_counts": dict(sorted(reason_counts.items())),
        "rejected_rows": len(rejected),
    }
    write_json(report, report_path)

    manifest: dict[str, object] = {
        "command": "clean-orders clean",
        "inputs": input_hashes,
        "outputs": {
            clean_path.name: sha256_file(clean_path),
            rejected_path.name: sha256_file(rejected_path),
            report_path.name: sha256_file(report_path),
        },
        "runtime": {
            "pandas": pd.__version__,
            "python": platform.python_version(),
        },
    }
    write_json(manifest, manifest_path)
    return report
