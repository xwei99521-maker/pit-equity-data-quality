# Point-in-Time Equity Data Quality

This project examines how filing availability and cross-filing revisions affect
historical equity fundamentals. It starts from SEC EDGAR Company Facts data and
retains the filing metadata needed to reconstruct what was known by a historical
cutoff date.

The current command inspects the structure of one company's SEC Company Facts
response. Point-in-time snapshots and revision analysis will build on the source
fields verified in this first step.

## Setup

Create a local `.env` file from `.env.example` and identify requests with a real
name and contact email, as required by the SEC's automated-access guidance.

```bash
python -m pip install -e ".[dev]"
python -m pit_equity inspect-sec --cik 0000320193
pytest
```

Raw and processed data are kept outside version control.
