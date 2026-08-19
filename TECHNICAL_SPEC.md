# Companion technical specification

This document is the reader-facing technical reference for the **Messy Orders Cleanup** companion that accompanies *Python for Data Engineering from Scratch* by Mason Ye. It states the contract the companion implements: what it requires as input, what it guarantees as output, and the exact rules by which it accepts or rejects a record. It is written to be read alongside the book. The companion carries a test suite that exercises many of these behaviors, but be precise about its reach: the suite does not directly exercise every behavior described here, and its canonical fixture produces only eleven of the twenty-six declared reason codes, so it does not directly exercise all twenty-six. What is described below is the implemented contract; the tests are bounded evidence for the specific cases they assert, not a demonstration of every behavior on this page.

## Runtime contract

- Package metadata requires CPython 3.12 or newer; that minimum is what the installer enforces.
- Execution has been verified on CPython 3.12.6 and CPython 3.14.6, each with pandas 3.0.5. These are the runtimes the companion was actually run and checked on, not a promise about other releases.
- pandas 3.0.5 is the one runtime dependency. When the local package is installed into a fresh virtual environment, pip may additionally fetch the declared build tooling (for example, a recent `setuptools`) to build and install the package; that tooling is used only at install time and is separate from the single runtime dependency.
- The workflow makes no use of a network, database, notebook, API key, or cloud service at run time.

## Canonical command

Run from the `companion` directory after installation:

```text
clean-orders clean --orders data/raw/orders.csv --customers data/raw/customers.json --output-dir data/out
```

On the included fixture this prints one summary line:

```text
INFO cleanup complete: input=20 accepted=9 rejected=11
```

## Input contract

The orders file must satisfy a structural contract before any business-rule cleaning runs, and both the standard-library example (`examples/first_cleanup.py`) and the canonical pandas workflow enforce it identically.

- **Header.** The header must be exactly the declared field names, in exactly this order: `order_id`, `customer_id`, `order_date`, `product`, `category`, `quantity`, `unit_price`, `paid`, `notes`. A missing, unexpected, or reordered header fails the run with a clear message. A UTF-8 byte-order mark is not stripped and therefore does not satisfy the exact first field name.
- **Blank physical lines and record width.** A physically empty line is not a logical CSV record and is ignored. Every non-empty logical CSV record must contain exactly the nine declared fields. A record with fewer or more fields is a run-level structural failure: the run stops with a message naming the offending logical record and its actual field count, before any record is cleaned. This is deliberate. A short record would otherwise let a structurally broken row masquerade as a genuinely missing field, and an over-wide record would let an extra source cell be silently dropped; rejecting wrong-width records outright preserves the missing-versus-blank distinction and loses no data silently. Both implementations call the same structural preflight, so they apply the same header, blank-line, and width policies and a file one accepts is a file the other accepts.
- **Customer reference.** The customer file must be a JSON array of customer objects, each with a non-empty string `customer_id`, a non-empty string `customer_name`, and a `contact` object whose `city` is a string. If two customers share the same `customer_id`, the loader stops with a clear error naming the duplicate id rather than allowing a later object to overwrite an earlier one. Both implementations reject duplicate customer ids the same way.

`source_row` is the logical CSV-record ordinal, with the header treated as position one; it is not guaranteed to equal a physical text-file line when valid CSV contains blank physical lines or embedded newlines. Under the nine-field contract, a structurally well-formed record's fields all arrive as strings; the contract exists precisely so that ragged records, which a CSV reader can otherwise represent with `None` or an extra list, are refused before cleaning rather than misread.

## Output contract

The workflow writes four files into the output directory, using two mechanisms:

- `orders_clean.csv`: accepted, normalized rows only, with the customer's name and city attached. Written by pandas with `DataFrame.to_csv`, in a fixed column order with an explicit line terminator and no index column.
- `orders_rejected.csv`: every rejected source row, preserved with its original values and one or more reason codes. Also written by pandas with `DataFrame.to_csv`.
- `quality_report.json`: bounded input, acceptance, rejection, and reason counts. Written by serializing a plain dictionary with `json.dumps` and writing the text with `Path.write_text`, not through pandas.
- `run_manifest.json`: the command name, the observed runtime versions, the two input SHA-256 identities, and the three non-manifest output SHA-256 identities. Written the same way as the report, with `json.dumps` and `Path.write_text`. It does not hash itself and records the command name rather than the full argument line.

The two CSV files are therefore pandas writes, and the two JSON files are standard-library JSON writes.

Raw input files are read-only and are never overwritten. Before any output write, the program resolves all input and planned output paths, rejects every input/output collision (including resolved symbolic-link aliases), and freezes both input hashes. An identical rerun on the same runtime reproduces the clean, rejected, and report files byte for byte; the manifest additionally records the observed runtime versions and so may legitimately differ across runtimes. Byte-for-byte identity across different machines or operating systems is not claimed.

## Duplicate contract

After field and reference validation, the last valid source row for a repeated `order_id` wins. Every earlier valid row is written to the reject output with `duplicate_order_id_superseded`. Invalid rows never supersede valid rows.

## Field states and reason codes

For required fields, an absent key or a `None` cell is `missing_*`; a present cell that becomes empty after whitespace normalization is `blank_*`. Invalid values, unknown customer references, zero quantities, and false booleans remain separate states, each with its own reason code. Missing, blank, invalid, unknown, and zero or false are never collapsed into one another.

The full implemented reason inventory has twenty-six codes: eight `blank_*` codes, eight `missing_*` codes, `invalid_*` codes for the seven validated fields (`order_id`, `customer_id`, `order_date`, `category`, `quantity`, `unit_price`, `paid`), `nonpositive_quantity`, `unknown_customer_id`, and `duplicate_order_id_superseded`. The canonical fixture exercises eleven of these codes, one row each, and its four present-but-empty cells use `blank_*` rather than `missing_*`. The complete list is given in Appendix C of the book.

## Accepted formats

- Order identifier: `ORD-` plus four digits after trimming and uppercasing.
- Customer identifier: `C` plus three digits after trimming and uppercasing.
- Order date: `YYYY-MM-DD` or `YYYY/MM/DD`; output is ISO `YYYY-MM-DD`.
- Quantity: base-10 integer greater than zero.
- Unit price: optional leading `$`, parseable as `Decimal`, zero or greater; output has exactly two decimal places. An extreme value that parses as a `Decimal` but cannot be quantized to two places is rejected as `invalid_unit_price` rather than crashing the run.
- Paid true values: `yes`, `y`, `true`, `1`. Paid false values: `no`, `n`, `false`, `0`.
- Categories: `stationery`, `home`, `electronics`, `office`; `kitchen` is the only declared alias and normalizes to `home`.

Required blank fields, invalid values, and unknown customer references are rejected rather than guessed or imputed.

## Evidence and its bounds

The companion's test suite runs on both verified runtimes and passes:

```text
Ran 32 tests

OK
```

A passing suite is bounded evidence that the tested behaviors, on the tested inputs, worked as expected; it is not proof that every possible data defect is caught. The end-to-end test makes several assertions together, over the input, accepted, and rejected totals, the full reason-count table, and specific surviving and superseded rows. Stable counts confirm that the tested inputs still land where they landed; they do not prove every transformation is correct in general, and the fixture does not exercise all twenty-six reason codes. The fixture is small and synthetic, the accepted rules are a declared teaching contract rather than universal business truth, and record-level quarantine (rejecting a bad record and continuing, while a structural failure halts the run) is this project's declared policy. No performance, scale, concurrency, cloud, database, security, compliance, or production-readiness claim is supported.
