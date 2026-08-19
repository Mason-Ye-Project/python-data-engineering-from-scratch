import unittest

from messy_orders.rules import (
    clean_text,
    normalize_category,
    parse_order_date,
    parse_paid,
    parse_quantity,
    parse_unit_price,
    source_rejection,
    validate_and_clean_order,
)

CUSTOMERS = {
    "C001": {"customer_name": "Avery Chen", "customer_city": "Example Bay"}
}


def valid_source() -> dict[str, object]:
    return {
        "source_row": 2,
        "order_id": " ORD-1001 ",
        "customer_id": "c001",
        "order_date": "2026/07/01",
        "product": "  Paper   Clips ",
        "category": " OFFICE ",
        "quantity": "2",
        "unit_price": "$1.995",
        "paid": " YES ",
        "notes": "  first   order ",
    }


class RuleTests(unittest.TestCase):
    def test_clean_text_collapses_whitespace(self) -> None:
        self.assertEqual(clean_text("  Paper   Clips  "), "Paper Clips")

    def test_date_accepts_only_declared_formats(self) -> None:
        self.assertEqual(parse_order_date("2026/07/01"), "2026-07-01")
        self.assertIsNone(parse_order_date("01-07-2026"))

    def test_quantity_distinguishes_invalid_and_nonpositive(self) -> None:
        self.assertIsNone(parse_quantity("2.5"))
        self.assertEqual(parse_quantity("0"), 0)

    def test_price_uses_decimal_rounding(self) -> None:
        self.assertEqual(parse_unit_price("$1.995"), "2.00")
        self.assertIsNone(parse_unit_price("NaN"))
        self.assertIsNone(parse_unit_price("-1.00"))
        self.assertIsNone(parse_unit_price("1e1000000"))

    def test_paid_domain_is_explicit(self) -> None:
        self.assertEqual(parse_paid("Y"), "true")
        self.assertEqual(parse_paid("0"), "false")
        self.assertIsNone(parse_paid("unknown"))

    def test_category_alias_is_bounded(self) -> None:
        self.assertEqual(normalize_category("Kitchen"), "home")
        self.assertIsNone(normalize_category("garden"))

    def test_valid_row_is_normalized_and_enriched(self) -> None:
        cleaned, reasons = validate_and_clean_order(valid_source(), CUSTOMERS)
        self.assertEqual(reasons, [])
        assert cleaned is not None
        self.assertEqual(cleaned["order_id"], "ORD-1001")
        self.assertEqual(cleaned["product"], "Paper Clips")
        self.assertEqual(cleaned["unit_price"], "2.00")
        self.assertEqual(cleaned["customer_city"], "Example Bay")

    def test_blank_invalid_and_unknown_are_separate(self) -> None:
        source = valid_source()
        source["order_id"] = ""
        source["quantity"] = "0"
        source["customer_id"] = "C999"
        cleaned, reasons = validate_and_clean_order(source, CUSTOMERS)
        self.assertIsNone(cleaned)
        self.assertEqual(
            reasons,
            ["blank_order_id", "unknown_customer_id", "nonpositive_quantity"],
        )

    def test_blank_and_missing_emit_distinct_codes(self) -> None:
        blank_source = valid_source()
        blank_source["product"] = "   "
        missing_source = valid_source()
        del missing_source["product"]

        blank_cleaned, blank_reasons = validate_and_clean_order(
            blank_source, CUSTOMERS
        )
        missing_cleaned, missing_reasons = validate_and_clean_order(
            missing_source, CUSTOMERS
        )

        self.assertIsNone(blank_cleaned)
        self.assertEqual(blank_reasons, ["blank_product"])
        self.assertIsNone(missing_cleaned)
        self.assertEqual(missing_reasons, ["missing_product"])

    def test_invalid_customer_identifier_has_specific_reason(self) -> None:
        source = valid_source()
        source["customer_id"] = "customer-1"
        cleaned, reasons = validate_and_clean_order(source, CUSTOMERS)
        self.assertIsNone(cleaned)
        self.assertEqual(reasons, ["invalid_customer_id"])

    def test_rejection_preserves_raw_source_cells(self) -> None:
        source = valid_source()
        rejected = source_rejection(source, ["example_reason"])
        self.assertEqual(rejected["order_id"], " ORD-1001 ")
        self.assertEqual(rejected["product"], "  Paper   Clips ")
        self.assertEqual(rejected["reason_codes"], "example_reason")


if __name__ == "__main__":
    unittest.main()
