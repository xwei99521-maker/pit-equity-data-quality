# Data Dictionary

The normalized facts table is written to `data/processed/sec/facts.parquet`.
Each row represents one reported SEC fact observation. Rows are not deduplicated
across filings because repeated reports and later revisions are inputs to the
point-in-time analysis.

| Column | Type | Description |
| --- | --- | --- |
| `cik` | string | Ten-digit SEC registrant identifier. |
| `ticker` | string | Case-study ticker from the issuer configuration. |
| `entity_name` | string | Registrant name returned by SEC Company Facts. |
| `canonical_concept` | string | Project concept defined in `config/concepts.csv`. |
| `period_type` | string | `instant` for a date balance or `duration` for an interval flow. |
| `taxonomy` | string | Original SEC taxonomy, currently `us-gaap`. |
| `tag` | string | Original XBRL concept tag. |
| `label` | string | Human-readable label supplied by the taxonomy. |
| `unit` | string | Original reported unit. It is not converted. |
| `value` | int64 | Reported whole-unit value from Company Facts. |
| `start_date` | date | Start of a duration fact; null for an instant fact. |
| `end_date` | date | Balance date or end of the reporting interval. |
| `filed_date` | date | Filing date reported by Company Facts. |
| `accession` | string | SEC filing accession number. |
| `form` | string | Filing form such as `10-K` or `10-Q`. |
| `fiscal_year` | int32 | Fiscal year supplied by Company Facts when present. |
| `fiscal_period` | string | Fiscal period such as `FY` or `Q1` when present. |
| `frame` | string | SEC calendar frame when present. |

The first mapping covers assets, liabilities, stockholders' equity, revenue,
and net income. Coverage is reported rather than inferred when a mapped source
tag is absent. Similar-looking tags are not treated as aliases unless they are
listed explicitly in `config/concepts.csv`.

The first revenue definition uses
`RevenueFromContractWithCustomerExcludingAssessedTax`. Broader `Revenues` and
sales-specific tags are not substituted because overlapping observations can
carry different values. This conservative choice favors consistent meaning over
maximum historical coverage.
