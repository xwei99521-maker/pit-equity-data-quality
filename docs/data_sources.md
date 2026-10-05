# Data Sources

## SEC EDGAR Company Facts

The initial source is the SEC's Company Facts API:

```text
https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json
```

The CIK is zero-padded to ten digits. Requests include a declared `User-Agent`
with a name and contact email. The SEC publishes a maximum automated-access rate
of ten requests per second; this project limits new downloads to approximately
four requests per second.

Each response is stored with a sidecar metadata file containing its source URL,
HTTP status, UTC fetch time, CIK, ticker, and entity name. The contact email is
sent in the request header but is not written to metadata. A response is reused
only when both its data and metadata files exist.

## Case-Study Issuers

The initial configuration contains twelve large SEC filers with different
industries and fiscal calendars. It is a data-structure test set, not a
historical or representative investment universe. Results from this set cannot
support claims about factor performance or the broader equity market.

Company Facts aggregates standard-taxonomy XBRL facts across a filer's
submissions. A fact observation can include `start`, `end`, `val`, `accn`, `fy`,
`fp`, `form`, `filed`, and `frame`. Not every field appears on every observation.
The `filed` date will be used as an initial end-of-day availability proxy, not as
an exact public dissemination timestamp.

References accessed August 28, 2026:

- https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- https://www.sec.gov/about/webmaster-frequently-asked-questions
- https://www.sec.gov/about/privacy-information
