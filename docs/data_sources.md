# Data Sources

## SEC EDGAR Company Facts

The initial source is the SEC's Company Facts API:

```text
https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json
```

The CIK is zero-padded to ten digits. Requests include a declared `User-Agent`
with a name and contact email and are cached before the project is expanded to
multiple issuers. The SEC publishes a maximum automated-access rate of ten
requests per second; this project will use a lower rate.

Company Facts aggregates standard-taxonomy XBRL facts across a filer's
submissions. A fact observation can include `start`, `end`, `val`, `accn`, `fy`,
`fp`, `form`, `filed`, and `frame`. Not every field appears on every observation.
The `filed` date will be used as an initial end-of-day availability proxy, not as
an exact public dissemination timestamp.

References accessed August 28, 2026:

- https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- https://www.sec.gov/about/webmaster-frequently-asked-questions
- https://www.sec.gov/about/privacy-information
