# Messy Orders Cleanup

This is the companion project for the book *Python for Data Engineering from Scratch* by Mason Ye. It is a small, self-contained program that reads a deliberately messy set of order records, cleans and validates them against a declared set of rules, and writes out the accepted records, the rejected records with reasons, a quality report, and a record of the run.

Everything here uses only synthetic, made-up data. There is no database, cloud account, API key, notebook, or paid tool involved, and the program makes no network calls when it runs. It is designed to be run, read, changed, and explained by someone who is learning, alongside the book.

## Getting this companion

This project is version 1.0.0. The primary way to obtain it is the pinned release, which is the exact version the book was written against:

```text
https://github.com/Mason-Ye-Project/python-data-engineering-from-scratch/releases/tag/v1.0.0-book
```

Download the companion archive from that release and unzip it to a folder you can find again; that folder is the project directory referred to below. If you would rather browse the project or want the most recent source, the repository is a secondary path:

```text
https://github.com/Mason-Ye-Project/python-data-engineering-from-scratch
```

Prefer the pinned release when following the book, because a pinned release does not move: its files are the 1.0.0 version the book's commands, outputs, and counts were verified against.

## What you need

- CPython 3.12 or newer. Check yours by running `python --version` (or `python3 --version` if `python` is not found), and use whichever command works wherever these instructions write `python`.
- An internet connection the first time you install, so the one dependency, pandas, can be downloaded.

Read the version facts as two separate statements. The package metadata requires CPython 3.12 or newer; that is the minimum the installer enforces. Separately, the companion was verified on CPython 3.12.6 and CPython 3.14.6, each with pandas 3.0.5; those are the exact runtimes it was actually run and checked on. The requirement is not a promise that every later Python or pandas release behaves identically, because only those two versions were verified.

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

When activation works, your prompt usually shows a `(.venv)` marker. Activation lasts only for the current terminal session, so if you open a new terminal you will need to move into the project and activate again.

Install the project:

```text
python -m pip install .
```

## Quick smoke test (optional first run)

Before the full workflow, you can run a small standard-library script to confirm your setup works. This early script uses only Python's built-in tools and cleans the same data in a simplified way, so a successful run means Python, your working directory, and the raw files are all in order.

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
Ran 20 tests

OK
```

A passing suite is bounded evidence that the tested behaviors, on the tested inputs, worked as expected. It is not proof that all possible data defects are caught.

## What the workflow writes

The command writes four files into the output directory you name (`data/out` above). Each has a distinct role:

- `orders_clean.csv` holds the accepted, normalized records, in a standard form with the customer's name and city attached.
- `orders_rejected.csv` holds every rejected row, preserved with its original values and a reason code explaining why it was rejected. Together with the clean file, this accounts for all twenty input rows.
- `quality_report.json` holds bounded counts: the input, accepted, and rejected totals, and how many times each rejection reason occurred.
- `run_manifest.json` records the run. It contains the command name (`clean-orders clean`), the observed runtime versions of Python and pandas, the content hashes of the two input files (`orders.csv` and `customers.json`), and the content hashes of the three non-manifest output files (`orders_clean.csv`, `orders_rejected.csv`, and `quality_report.json`). It does not hash itself, because a file cannot contain its own final hash, and it records the command name rather than the full argument line.

A content hash here is a short string computed from a file's exact bytes; it is a collision-resistant fingerprint, not a mathematical one-to-one proof, so it is extremely unlikely, rather than impossible in principle, for two different files to share one. That is enough to make comparing hashes a reliable, quick way to check whether two files are byte-for-byte the same.

## Raw data is never overwritten

The two input files, `data/raw/orders.csv` and `data/raw/customers.json`, are the source of truth and are read only. The workflow reads them and writes all of its results into the separate output directory; it never writes over the raw inputs. If you delete the output directory, you can always regenerate it by running the command again from the untouched raw files. If you want to experiment with the input, copy it somewhere else first and change the copy, leaving the raw files intact. Note that the cleaning transformations themselves (whitespace collapsing, uppercasing identifiers, lowercasing categories, two-decimal rounding) are one-way; what makes a cleaning decision recoverable is that the raw file is preserved, not that the transformation can be reversed.

## Reproducibility

Running the command twice on the same data and the same runtime produces byte-for-byte identical `orders_clean.csv`, `orders_rejected.csv`, and `quality_report.json`, and therefore identical content hashes for them. This byte-for-byte claim is bounded to an identical rerun on the same frozen runtime (the verified Python versions with pandas 3.0.5); it is not a claim that the outputs are byte-identical across different machines or operating systems, which was not tested. The `run_manifest.json` records the observed Python and pandas versions, so it can legitimately differ if you run on a different runtime; on the same runtime, an identical rerun reproduces it too.

## Troubleshooting

- **"No such file or directory" for an input file.** You are probably running from the wrong directory. Confirm where you are with `pwd` (macOS or Linux) or `Get-Location` (Windows PowerShell), and move into this project directory before running the command.
- **`python` not found, or the wrong version.** Try `python3` instead, and use that name throughout. If you have no suitable version, install CPython 3.12 or newer from python.org.
- **pandas seems to be missing.** The virtual environment is probably not active. Look for the `(.venv)` marker on your prompt; if it is absent, activate the environment again with the command for your system and rerun.
- **PowerShell blocks the activation script on Windows.** This is a common first-time issue. PowerShell's own documentation describes adjusting the execution policy to allow local scripts for your user account; apply that and activate again.
- **The counts are not 20, 9, and 11.** Confirm you are running against the unmodified raw files in `data/raw`, not an altered copy.

## Limitations

This companion is a learning project, and it is honest about its bounds. The data and people are synthetic and fictional. The fixture is small, so nothing here demonstrates performance, scale, or behavior on large or differently shaped data. The cleaning rules are a declared teaching contract chosen for this project, not universal truths about order data; a different purpose could justify different rules, and record-level quarantine (rejecting a bad record and continuing) is this project's declared policy rather than a universal rule. A passing test suite is bounded evidence that the tested behaviors worked on the tested data, not proof that all possible data defects are caught. Running and understanding this project is a genuine learning accomplishment, but it is not professional experience, job readiness, or production readiness.

## License

The companion code is released under the MIT License. See the `LICENSE` file for the full text.
