# Messy Orders Cleanup

This is the companion project for the book *Python for Data Engineering from Scratch* by Mason Ye. It is a small, self-contained program that reads a deliberately messy set of order records, cleans and validates them against a declared set of rules, and writes out the accepted records, the rejected records with reasons, a quality report, and a record of the run.

Everything here uses only synthetic, made-up data. There is no database, cloud account, API key, notebook, or paid tool involved, and the program makes no network calls when it runs. It is designed to be run, read, changed, and explained by someone who is learning, alongside the book.

## Getting this companion

This project is version 1.0.3. The primary way to obtain it is the versioned release, which is the version the book was written against:

```text
https://github.com/Mason-Ye-Project/python-data-engineering-from-scratch/releases/tag/v1.0.3-book
```

On that release page, download the companion archive named `Python_for_Data_Engineering_from_Scratch_Companion_v1.0.3.zip` and unzip it to a folder you can find again; that folder is the project directory referred to below. If you would rather browse the project or want the most recent source, the repository is a secondary path:

```text
https://github.com/Mason-Ye-Project/python-data-engineering-from-scratch
```

Prefer the versioned release when following the book: it is the 1.0.3 version the book's commands, outputs, and counts were verified against, so following along against it gives you the results shown in these pages.

## What you need

- CPython 3.12 or newer. Check yours by running `python --version` (or `python3 --version` if `python` is not found), and use whichever command works wherever these instructions write `python`.
- An internet connection the first time you install, so the dependency can be downloaded.

Read the version facts as two separate statements. The package metadata requires CPython 3.12 or newer; that is the minimum the installer enforces. Separately, the companion was verified on CPython 3.12.6 and CPython 3.14.6, each with pandas 3.0.5; those are the exact runtimes it was actually run and checked on. The requirement is not a promise that every later Python or pandas release behaves identically, because only those two versions were verified.

## Dependencies

The companion has exactly one runtime dependency: pandas, pinned to version 3.0.5. That is the only third-party package the program itself imports when it runs. When you install the project into a fresh virtual environment, pip may also briefly fetch the small build tooling the project declares (for example, a recent `setuptools`) in order to build and install the local package; that build tooling is separate from the single runtime dependency and is used only during installation, not when the workflow runs.

## Set up

Open a terminal (Terminal on macOS, PowerShell on Windows, your terminal application on Linux) and move into this project directory with `cd`. Then create and activate a virtual environment, which is a private space for this project's dependency.

Create it:

```text
python -m venv .venv
```

Activate it. On macOS or Linux:

```bash
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

When activation works, your prompt may show a `(.venv)` marker. Activation lasts only for the current terminal session, so if you open a new terminal you will need to move into the project and activate again.

Install the project:

```text
python -m pip install .
```

## Quick smoke test (optional first run)

Before the full workflow, you can run a small standard-library script to confirm that the interpreter you invoked can import the installed companion and read the specified raw files. This early script uses only Python's built-in tools and cleans the same data in a simplified way.

With the environment active, run:

```text
python examples/first_cleanup.py --orders data/raw/orders.csv --customers data/raw/customers.json --output-dir data/first_out
```

It prints one line:

```text
input=20 accepted=9 rejected=11
```

This early script writes two interim files, `first_clean.csv` and `first_rejected.csv`, into `data/first_out`. That is different from the finished `clean-orders` workflow below, which writes the four canonical outputs (`orders_clean.csv`, `orders_rejected.csv`, `quality_report.json`, and `run_manifest.json`) into `data/out`. The smoke test is just a quick check that your setup runs; the `clean-orders` command is the complete workflow.

## Run the cleaning workflow

With the environment active, run the finished command from this directory:

```text
clean-orders clean --orders data/raw/orders.csv --customers data/raw/customers.json --output-dir data/out
```

When it runs on the included data, it prints one summary line:

```text
INFO cleanup complete: input=20 accepted=9 rejected=11
```

That means it read twenty input rows, accepted nine, and rejected eleven. Nine plus eleven is twenty, so every row is accounted for.

## Run the tests

The project comes with a test suite. Run it with:

```text
python -m unittest discover -s tests -v
```

When everything passes, the run ends with:

```text
Ran 32 tests

OK
```

A passing suite is bounded evidence that the tested behaviors, on the tested inputs, worked as expected. It is not proof that all possible data defects are caught. The end-to-end test makes several assertions together, checking the input, accepted, and rejected totals, the full table of reason counts, and specific surviving and superseded rows; the canonical fixture exercises eleven of the twenty-six declared reason codes, so the suite does not directly exercise all twenty-six.

## Input structure the loader requires

Both the standard-library example and the canonical `clean-orders` workflow read the orders through one shared parser, `load_orders_csv_records`, which parses the file once with the standard library's strict CSV reader and returns the records both workflows clean; neither path reparses the orders with `DictReader` or `pandas.read_csv`. That single reader enforces the whole contract: it rejects an embedded NUL character and malformed or unclosed quoting, requires the header to be exactly the declared nine field names in the declared order, and does not silently strip a UTF-8 byte-order mark, so a BOM header fails the header check. A physically empty line after the header is skipped because it is not a logical CSV record, while a blank line before the header is rejected. Every data record must contain exactly nine fields; a record with too few or too many fields is a run-level structural failure, and the run stops with a clear message naming the offending logical record and its field count, rather than silently collapsing a missing cell or discarding an extra one. Because both workflows consume the records this one reader produced, a file it accepts is accepted for both and a file it rejects is rejected for both. This structural parsing is deliberately separate from, and earlier than, the per-record business rules that reject an individual row for a blank required value, an invalid format, or an unknown customer.

The customer reference file is held to a matching standard by one shared strict JSON decoder. That decoder rejects a duplicate member name inside any single JSON object, at the top level or nested, so a customer object that repeats `customer_id`, or a `contact` object that repeats `city`, is a run-level reference-file failure rather than being silently resolved to the last value. This is distinct from, and earlier than, the duplicate-customer rule: after decoding, if two separate customer objects share the same `customer_id`, the loader still stops with a clear error naming the duplicate id rather than silently letting one overwrite the other. Both implementations decode the reference file the same strict way and reject both duplicate member names and duplicate customer ids.

## What the workflow writes

The command writes four files into the output directory you name (`data/out` above). Each has a distinct role, and the program writes them with two different mechanisms:

- `orders_clean.csv` holds the accepted, normalized records, in a standard form with the customer's name and city attached. It is written by pandas with `DataFrame.to_csv`.
- `orders_rejected.csv` holds every rejected row, preserved with its original values and a reason code explaining why it was rejected. Together with the clean file, this accounts for all twenty input rows. It is also written by pandas with `DataFrame.to_csv`.
- `quality_report.json` holds bounded counts: the input, accepted, and rejected totals, and how many times each rejection reason occurred. It is written not through pandas but by serializing a plain Python dictionary with `json.dumps` and writing the text with `Path.write_text`.
- `run_manifest.json` records the run. It contains the command name (`clean-orders clean`), the observed runtime versions of Python and pandas, the content hashes of the two input files (`orders.csv` and `customers.json`), and the content hashes of the three non-manifest output files (`orders_clean.csv`, `orders_rejected.csv`, and `quality_report.json`). Like the report, it is written with `json.dumps` and `Path.write_text`. It does not hash itself, because a file cannot contain its own final hash, and it records the command name rather than the full argument line.

So the two CSV files come from pandas, and the two JSON files come from standard-library JSON serialization; neither JSON file passes through pandas.

A content hash here is a short string computed from a file's exact bytes; it is a collision-resistant fingerprint, not a mathematical one-to-one proof, so it is extremely unlikely, rather than impossible in principle, for two different files to share one. That is enough to make comparing hashes a reliable, quick way to check whether two files are byte-for-byte the same.

## Raw data is never overwritten

The two input files, `data/raw/orders.csv` and `data/raw/customers.json`, are the source of truth and are read only. Before writing anything, each workflow resolves every input path and every planned output path and refuses several kinds of alias: a direct input/output collision; a filesystem-identity alias, such as an output that is a hard link to a raw input, checked by identity rather than by comparing path text; a pre-existing output that is a symbolic link; and an output that aliases another output. Every resolved output must also stay inside the resolved output directory, and the manifest records the declared output names rather than whatever basename a resolved target might have. The canonical workflow also freezes both input hashes before it writes its first output. Together these checks stop the run before it could write over a raw input, write outside the output directory, or record an output's replacement bytes as an input identity. They guard against the alias patterns just described; they are not a promise of safety against every possible race or a filesystem that is changed by something else mid-run. If you delete the output directory, you can regenerate it by running the command again from the untouched raw files. If you want to experiment with the input, copy it somewhere else first and change the copy, leaving the raw files intact. Note that the cleaning transformations themselves (whitespace collapsing, uppercasing identifiers, lowercasing categories, two-decimal rounding) are one-way; what makes a cleaning decision recoverable is that the raw file is preserved, not that the transformation can be reversed.

## Reproducibility

Running the command twice on the same data and the same runtime produces byte-for-byte identical `orders_clean.csv`, `orders_rejected.csv`, and `quality_report.json`, and therefore identical content hashes for them. This byte-for-byte claim is bounded to an identical rerun on the same frozen runtime (the verified Python versions with pandas 3.0.5); it is not a claim that the outputs are byte-identical across different machines or operating systems, which was not tested. The `run_manifest.json` records the observed Python and pandas versions, so it can legitimately differ if you run on a different runtime; on the same runtime, an identical rerun reproduces it too.

## Troubleshooting

- **"No such file or directory" for an input file.** Check the working directory first with `pwd` (macOS or Linux) or `Get-Location` (Windows PowerShell), and move into this project directory before running the command. If the directory is correct, verify the input path and filename next.
- **`python` not found, or the wrong version.** Try `python3` instead, and use that name throughout. If you have no suitable version, install CPython 3.12 or newer from python.org.
- **pandas seems to be missing.** One possible cause is that the command invoked an interpreter where the companion is not installed. Check which interpreter the command uses, activate the intended environment if needed, run `python -m pip install .` there, and rerun.
- **PowerShell blocks the activation script on Windows.** PowerShell's own documentation describes adjusting the execution policy to allow local scripts for your user account; follow that guidance and activate again.
- **The counts are not 20, 9, and 11.** Confirm you are running against the unmodified raw files in `data/raw`, not an altered copy.
- **The run stops complaining a record has the wrong number of fields.** That is the nine-field structural check. Look at the record number it names in `data/raw/orders.csv` and confirm the file has not been edited into a short or over-wide row.
- **A run failed but old output files are still in the directory.** A failed run does not delete outputs from an earlier successful run, and the current implementation does not write outputs atomically. So after a failed run the error status is current while any files already in the output directory are stale, left over from the previous successful run. Use a fresh output directory or clear the old directory before investigating a new run, so you do not read an old clean file, report, or manifest as if it came from the run that just failed.

## Limitations

This companion is a learning project, and it is honest about its bounds. The data and people are synthetic and fictional. The fixture is small, so nothing here demonstrates performance, scale, or behavior on large or differently shaped data. The cleaning rules are a declared teaching contract chosen for this project, not universal truths about order data; a different purpose could justify different rules, and record-level quarantine (rejecting a bad record and continuing) is this project's declared policy rather than a universal rule. A passing test suite is bounded evidence that the tested behaviors worked on the tested data, not proof that all possible data defects are caught. Running and understanding this project is a genuine learning accomplishment, but it is not professional experience, job readiness, or production readiness.

## License

The companion code is released under the MIT License. See the `LICENSE` file for the full text.
