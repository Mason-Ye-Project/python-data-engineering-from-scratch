import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


EXAMPLE_PATH = Path(__file__).resolve().parents[1] / "examples" / "first_cleanup.py"
EXAMPLE_SPEC = importlib.util.spec_from_file_location(
    "first_cleanup_example", EXAMPLE_PATH
)
if EXAMPLE_SPEC is None or EXAMPLE_SPEC.loader is None:
    raise RuntimeError(f"cannot load example module: {EXAMPLE_PATH}")
EXAMPLE_MODULE = importlib.util.module_from_spec(EXAMPLE_SPEC)
EXAMPLE_SPEC.loader.exec_module(EXAMPLE_MODULE)
load_customers = EXAMPLE_MODULE.load_customers
load_orders = EXAMPLE_MODULE.load_orders


HEADER = (
    "order_id,customer_id,order_date,product,category,quantity,"
    "unit_price,paid,notes\n"
)


class FirstCleanupInputTests(unittest.TestCase):
    def test_duplicate_customer_id_fails_clearly(self) -> None:
        payload = [
            {
                "customer_id": "C001",
                "customer_name": "First Customer",
                "contact": {"city": "Example Bay"},
            },
            {
                "customer_id": "C001",
                "customer_name": "Replacement Customer",
                "contact": {"city": "Example Point"},
            },
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "customers.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate customer_id: C001"):
                load_customers(path)

    def test_short_csv_record_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "orders.csv"
            path.write_text(
                HEADER + "ORD-9001,C001,2026-07-01,Notebook,stationery,1,4.50,yes\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "row 2 has 8 fields; expected 9"):
                load_orders(path)

    def test_extra_csv_field_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "orders.csv"
            path.write_text(
                HEADER
                + "ORD-9001,C001,2026-07-01,Notebook,stationery,1,4.50,yes,ok,extra\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "row 2 has 10 fields; expected 9"):
                load_orders(path)
