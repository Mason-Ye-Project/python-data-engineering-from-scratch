"""Standard-library vertical slice for the opening chapter."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from messy_orders.input_contract import plan_safe_io_paths, validate_orders_csv_structure
from messy_orders.rules import (
    CLEAN_FIELDS,
    REJECT_FIELDS,
    source_rejection,
    validate_and_clean_order,
)


def load_customers(path: Path) -> dict[str, dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("customers JSON must contain an array")

    customers: dict[str, dict[str, str]] = {}
    for customer in payload:
        if not isinstance(customer, dict):
            raise ValueError("each customer must be a JSON object")
        customer_id = customer.get("customer_id")
        customer_name = customer.get("customer_name")
        contact = customer.get("contact")
        if not isinstance(customer_id, str) or not customer_id:
            raise ValueError("each customer requires customer_id text")
        if not isinstance(customer_name, str) or not customer_name:
            raise ValueError(f"customer {customer_id} requires customer_name text")
        if not isinstance(contact, dict) or not isinstance(contact.get("city"), str):
            raise ValueError(f"customer {customer_id} requires contact.city text")
        if customer_id in customers:
            raise ValueError(f"duplicate customer_id: {customer_id}")
        customers[customer_id] = {
            "customer_name": customer["customer_name"],
            "customer_city": customer["contact"]["city"],
        }
    return customers


def load_orders(path: Path) -> list[dict[str, object]]:
    validate_orders_csv_structure(path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, object]] = []
        # This is a logical CSV-record ordinal. The header occupies position 1.
        for source_row, row in enumerate(reader, start=2):
            row["source_row"] = source_row
            rows.append(row)
    return rows


def write_rows(
    path: Path, fields: tuple[str, ...], rows: list[dict[str, object]]
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run(
    orders_path: Path, customers_path: Path, output_dir: Path
) -> tuple[int, int, int]:
    inputs, output_dir, outputs = plan_safe_io_paths(
        {"orders": orders_path, "customers": customers_path},
        output_dir,
        ("first_clean.csv", "first_rejected.csv"),
    )
    orders_path = inputs["orders"]
    customers_path = inputs["customers"]
    customers = load_customers(customers_path)
    orders = load_orders(orders_path)

    valid_candidates: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []
    source_by_row = {int(row["source_row"]): row for row in orders}

    for row in orders:
        cleaned, reasons = validate_and_clean_order(row, customers)
        if cleaned is None:
            rejected.append(source_rejection(row, reasons))
        else:
            valid_candidates.append(cleaned)

    last_row_for_order = {
        str(row["order_id"]): int(row["source_row"]) for row in valid_candidates
    }
    accepted: list[dict[str, object]] = []
    for row in valid_candidates:
        if int(row["source_row"]) == last_row_for_order[str(row["order_id"])]:
            accepted.append(row)
        else:
            rejected.append(
                source_rejection(
                    source_by_row[int(row["source_row"])],
                    ["duplicate_order_id_superseded"],
                )
            )

    accepted.sort(key=lambda row: int(row["source_row"]))
    rejected.sort(key=lambda row: int(row["source_row"]))
    output_dir.mkdir(parents=True, exist_ok=True)
    write_rows(outputs["first_clean.csv"], CLEAN_FIELDS, accepted)
    write_rows(outputs["first_rejected.csv"], REJECT_FIELDS, rejected)
    return len(orders), len(accepted), len(rejected)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--orders", type=Path, required=True)
    parser.add_argument("--customers", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    input_rows, accepted_rows, rejected_rows = run(
        args.orders,
        args.customers,
        args.output_dir,
    )
    print(f"input={input_rows} accepted={accepted_rows} " f"rejected={rejected_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
