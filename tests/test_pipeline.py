import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from messy_orders.cli import main
from messy_orders.pipeline import clean_orders, load_orders, run_pipeline

COMPANION_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = COMPANION_ROOT / "data" / "raw"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PipelineTests(unittest.TestCase):
    def test_end_to_end_counts_and_reason_codes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            report = run_pipeline(
                RAW_ROOT / "orders.csv",
                RAW_ROOT / "customers.json",
                output_dir,
            )

            self.assertEqual(report["input_rows"], 20)
            self.assertEqual(report["accepted_rows"], 9)
            self.assertEqual(report["rejected_rows"], 11)
            self.assertEqual(
                report["reason_counts"],
                {
                    "duplicate_order_id_superseded": 1,
                    "blank_order_date": 1,
                    "blank_order_id": 1,
                    "blank_product": 1,
                    "blank_quantity": 1,
                    "invalid_category": 1,
                    "invalid_order_date": 1,
                    "invalid_paid": 1,
                    "invalid_unit_price": 1,
                    "nonpositive_quantity": 1,
                    "unknown_customer_id": 1,
                },
            )

            with (output_dir / "orders_clean.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                clean_rows = list(csv.DictReader(handle))
            corrected = [row for row in clean_rows if row["order_id"] == "ORD-1012"]
            self.assertEqual(len(corrected), 1)
            self.assertEqual(corrected[0]["quantity"], "6")
            self.assertEqual(corrected[0]["source_row"], "14")

            with (output_dir / "orders_rejected.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rejected_rows = list(csv.DictReader(handle))
            superseded = [
                row
                for row in rejected_rows
                if row["reason_codes"] == "duplicate_order_id_superseded"
            ]
            self.assertEqual(len(superseded), 1)
            self.assertEqual(superseded[0]["source_row"], "13")
            self.assertEqual(superseded[0]["quantity"], "5")
            self.assertEqual(superseded[0]["notes"], "earlier duplicate")

    def test_identical_rerun_is_byte_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            run_pipeline(
                RAW_ROOT / "orders.csv",
                RAW_ROOT / "customers.json",
                output_dir,
            )
            names = (
                "orders_clean.csv",
                "orders_rejected.csv",
                "quality_report.json",
                "run_manifest.json",
            )
            first = {name: digest(output_dir / name) for name in names}
            run_pipeline(
                RAW_ROOT / "orders.csv",
                RAW_ROOT / "customers.json",
                output_dir,
            )
            second = {name: digest(output_dir / name) for name in names}
            self.assertEqual(first, second)

    def test_raw_inputs_are_not_modified(self) -> None:
        before = {
            path.name: digest(path)
            for path in (RAW_ROOT / "orders.csv", RAW_ROOT / "customers.json")
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_pipeline(
                RAW_ROOT / "orders.csv",
                RAW_ROOT / "customers.json",
                Path(temporary_directory),
            )
        after = {
            path.name: digest(path)
            for path in (RAW_ROOT / "orders.csv", RAW_ROOT / "customers.json")
        }
        self.assertEqual(before, after)

    def test_manifest_binds_inputs_and_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            run_pipeline(
                RAW_ROOT / "orders.csv",
                RAW_ROOT / "customers.json",
                output_dir,
            )
            manifest = json.loads((output_dir / "run_manifest.json").read_text())
            self.assertEqual(
                manifest["inputs"]["orders.csv"],
                digest(RAW_ROOT / "orders.csv"),
            )
            self.assertEqual(
                manifest["outputs"]["orders_clean.csv"],
                digest(output_dir / "orders_clean.csv"),
            )

    def test_invalid_later_duplicate_does_not_supersede_valid_row(self) -> None:
        customers = {
            "C001": {
                "customer_name": "Avery Chen",
                "customer_city": "Example Bay",
            }
        }
        base = {
            "order_id": "ORD-2001",
            "customer_id": "C001",
            "order_date": "2026-07-10",
            "product": "Notebook",
            "category": "stationery",
            "quantity": "1",
            "unit_price": "4.50",
            "paid": "yes",
            "notes": "valid first row",
            "source_row": 2,
        }
        invalid_later = {**base, "paid": "maybe", "source_row": 3}
        accepted, rejected = clean_orders([base, invalid_later], customers)
        self.assertEqual([row["source_row"] for row in accepted], [2])
        self.assertEqual(rejected[0]["reason_codes"], "invalid_paid")

    def test_missing_csv_header_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "orders.csv"
            path.write_text("order_id,customer_id\nORD-1001,C001\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing headers"):
                load_orders(path)

    def test_reordered_csv_header_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "orders.csv"
            path.write_text(
                "customer_id,order_id,order_date,product,category,quantity,"
                "unit_price,paid,notes\n"
                "C001,ORD-1001,2026-07-01,Notebook,stationery,1,4.50,yes,ok\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "out of order"):
                load_orders(path)

    def test_short_csv_record_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "orders.csv"
            path.write_text(
                "order_id,customer_id,order_date,product,category,quantity,"
                "unit_price,paid,notes\n"
                "ORD-9001,C001,2026-07-01,Notebook,stationery,1,4.50,yes\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "row 2 has 8 fields; expected 9"):
                load_orders(path)

    def test_extra_csv_field_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "orders.csv"
            path.write_text(
                "order_id,customer_id,order_date,product,category,quantity,"
                "unit_price,paid,notes\n"
                "ORD-9001,C001,2026-07-01,Notebook,stationery,1,4.50,yes,ok,extra\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "row 2 has 10 fields; expected 9"):
                load_orders(path)

    def test_extreme_price_is_rejected_instead_of_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            orders_path = root / "orders.csv"
            orders_path.write_text(
                "order_id,customer_id,order_date,product,category,quantity,"
                "unit_price,paid,notes\n"
                "ORD-9001,C001,2026-07-01,Notebook,stationery,1,"
                "1e1000000,yes,extreme price\n",
                encoding="utf-8",
            )
            report = run_pipeline(
                orders_path,
                RAW_ROOT / "customers.json",
                root / "out",
            )
            self.assertEqual(report["accepted_rows"], 0)
            self.assertEqual(report["rejected_rows"], 1)
            self.assertEqual(report["reason_counts"], {"invalid_unit_price": 1})

    def test_cli_returns_nonzero_when_input_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = main(
                [
                    "clean",
                    "--orders",
                    str(Path(temporary_directory) / "missing.csv"),
                    "--customers",
                    str(RAW_ROOT / "customers.json"),
                    "--output-dir",
                    str(Path(temporary_directory) / "out"),
                ]
            )
            self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
