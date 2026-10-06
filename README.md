# Point-in-Time Equity Data Quality

This project examines how filing availability and cross-filing revisions affect
historical equity fundamentals. It starts from SEC EDGAR Company Facts data and
retains the filing metadata needed to reconstruct what was known by a historical
cutoff date.

The pipeline can inspect one Company Facts response or cache raw responses for
a fixed case-study issuer set. The set is designed to expose different filing
structures and is not a representative investment universe. Point-in-time
snapshots and revision analysis will build on the retained source fields.

## Setup

Create a local `.env` file from `.env.example` and identify requests with a real
name and contact email, as required by the SEC's automated-access guidance.

```bash
python -m pip install -e ".[dev]"
python -m pit_equity inspect-sec --cik 0000320193
python -m pit_equity ingest-sec --issuers config/issuers.csv
python -m pit_equity build-facts
pytest
```

The ingestion command writes API responses and request metadata under
`data/raw/sec/companyfacts`. A second run uses the complete local cache instead
of downloading the same issuer again. Raw and processed data are kept outside
version control.

The normalization command applies the explicit mappings in
`config/concepts.csv` and writes a typed Parquet table under
`data/processed/sec`. It preserves the original taxonomy, tag, unit, reporting
period, filing date, form, and accession number. Missing concept coverage is
reported rather than filled with inferred values.
