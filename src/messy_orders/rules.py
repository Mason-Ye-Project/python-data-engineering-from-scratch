"""Pure cleaning and validation rules used by both companion implementations."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, DecimalException

ORDER_ID_PATTERN = re.compile(r"^ORD-\d{4}$")
CUSTOMER_ID_PATTERN = re.compile(r"^C\d{3}$")
DATE_PATTERN = re.compile(r"^\d{4}(?P<separator>[-/])\d{2}(?P=separator)\d{2}$")
CATEGORY_ALIASES = {"kitchen": "home"}
ALLOWED_CATEGORIES = {"stationery", "home", "electronics", "office"}
TRUE_VALUES = {"yes", "y", "true", "1"}
FALSE_VALUES = {"no", "n", "false", "0"}

SOURCE_FIELDS = (
    "order_id",
    "customer_id",
    "order_date",
    "product",
    "category",
    "quantity",
    "unit_price",
    "paid",
    "notes",
)

CLEAN_FIELDS = (
    "order_id",
    "customer_id",
    "order_date",
    "product",
    "category",
    "quantity",
    "unit_price",
    "paid",
    "notes",
    "customer_name",
    "customer_city",
    "source_row",
)

REJECT_FIELDS = (
    "source_row",
    *SOURCE_FIELDS,
    "reason_codes",
)


def clean_text(value: object) -> str:
    """Return trimmed text with repeated internal whitespace collapsed."""

    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def required_text_state(source: Mapping[str, object], field: str) -> tuple[str, str]:
    """Return missing, blank, or present plus normalized text for a field."""

    if field not in source or source[field] is None:
        return "missing", ""
    text = clean_text(source[field])
    if not text:
        return "blank", ""
    return "present", text


def normalize_identifier(value: object, pattern: re.Pattern[str]) -> str | None:
    text = clean_text(value).upper()
    if not text or pattern.fullmatch(text) is None:
        return None
    return text


def parse_order_date(value: object) -> str | None:
    text = clean_text(value)
    if DATE_PATTERN.fullmatch(text) is None:
        return None
    try:
        return date.fromisoformat(text.replace("/", "-")).isoformat()
    except ValueError:
        return None


def parse_quantity(value: object) -> int | None:
    text = clean_text(value)
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def parse_unit_price(value: object) -> str | None:
    text = clean_text(value).removeprefix("$")
    try:
        parsed = Decimal(text)
        if not parsed.is_finite() or parsed < 0:
            return None
        quantized = parsed.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except DecimalException:
        return None
    return str(quantized)


def parse_paid(value: object) -> str | None:
    text = clean_text(value).lower()
    if text in TRUE_VALUES:
        return "true"
    if text in FALSE_VALUES:
        return "false"
    return None


def normalize_category(value: object) -> str | None:
    text = clean_text(value).lower()
    text = CATEGORY_ALIASES.get(text, text)
    if text not in ALLOWED_CATEGORIES:
        return None
    return text


def validate_and_clean_order(
    source: Mapping[str, object],
    customers: Mapping[str, Mapping[str, str]],
) -> tuple[dict[str, object] | None, list[str]]:
    """Validate one source row and return either a clean row or reason codes."""

    reasons: list[str] = []
    source_row = int(source["source_row"])

    order_id_state, raw_order_id = required_text_state(source, "order_id")
    order_id = normalize_identifier(raw_order_id, ORDER_ID_PATTERN)
    if order_id_state != "present":
        reasons.append(f"{order_id_state}_order_id")
    elif order_id is None:
        reasons.append("invalid_order_id")

    customer_id_state, raw_customer_id = required_text_state(source, "customer_id")
    customer_id = normalize_identifier(raw_customer_id, CUSTOMER_ID_PATTERN)
    if customer_id_state != "present":
        reasons.append(f"{customer_id_state}_customer_id")
    elif customer_id is None:
        reasons.append("invalid_customer_id")
    elif customer_id not in customers:
        reasons.append("unknown_customer_id")

    date_state, raw_date = required_text_state(source, "order_date")
    order_date = parse_order_date(raw_date)
    if date_state != "present":
        reasons.append(f"{date_state}_order_date")
    elif order_date is None:
        reasons.append("invalid_order_date")

    product_state, product = required_text_state(source, "product")
    if product_state != "present":
        reasons.append(f"{product_state}_product")

    category_state, raw_category = required_text_state(source, "category")
    category = normalize_category(raw_category)
    if category_state != "present":
        reasons.append(f"{category_state}_category")
    elif category is None:
        reasons.append("invalid_category")

    quantity_state, raw_quantity = required_text_state(source, "quantity")
    quantity = parse_quantity(raw_quantity)
    if quantity_state != "present":
        reasons.append(f"{quantity_state}_quantity")
    elif quantity is None:
        reasons.append("invalid_quantity")
    elif quantity <= 0:
        reasons.append("nonpositive_quantity")

    price_state, raw_price = required_text_state(source, "unit_price")
    unit_price = parse_unit_price(raw_price)
    if price_state != "present":
        reasons.append(f"{price_state}_unit_price")
    elif unit_price is None:
        reasons.append("invalid_unit_price")

    paid_state, raw_paid = required_text_state(source, "paid")
    paid = parse_paid(raw_paid)
    if paid_state != "present":
        reasons.append(f"{paid_state}_paid")
    elif paid is None:
        reasons.append("invalid_paid")

    notes = clean_text(source.get("notes"))

    if reasons:
        return None, reasons

    assert order_id is not None
    assert customer_id is not None
    assert order_date is not None
    assert category is not None
    assert quantity is not None
    assert unit_price is not None
    assert paid is not None

    customer = customers[customer_id]
    clean_row: dict[str, object] = {
        "order_id": order_id,
        "customer_id": customer_id,
        "order_date": order_date,
        "product": product,
        "category": category,
        "quantity": quantity,
        "unit_price": unit_price,
        "paid": paid,
        "notes": notes,
        "customer_name": customer["customer_name"],
        "customer_city": customer["customer_city"],
        "source_row": source_row,
    }
    return clean_row, []


def source_rejection(
    source: Mapping[str, object], reasons: list[str]
) -> dict[str, object]:
    rejected: dict[str, object] = {"source_row": int(source["source_row"])}
    for field in SOURCE_FIELDS:
        raw_value = source.get(field)
        rejected[field] = "" if raw_value is None else str(raw_value)
    rejected["reason_codes"] = "|".join(reasons)
    return rejected
