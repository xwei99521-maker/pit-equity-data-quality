import json
from pathlib import Path

import pytest
import requests

from pit_equity.ingest_sec import (
    Issuer,
    companyfacts_paths,
    ingest_issuer,
    ingest_issuers,
    load_issuers,
    write_failure_report,
)


def test_load_issuers_normalizes_cik(tmp_path: Path) -> None:
    issuer_file = tmp_path / "issuers.csv"
    issuer_file.write_text(
        "cik,ticker,name\n320193,AAPL,Apple Inc.\n", encoding="utf-8"
    )

    assert load_issuers(issuer_file) == [
        Issuer(cik="0000320193", ticker="AAPL", name="Apple Inc.")
    ]


def test_load_issuers_rejects_duplicate_ciks(tmp_path: Path) -> None:
    issuer_file = tmp_path / "issuers.csv"
    issuer_file.write_text(
        "cik,ticker,name\n320193,AAPL,Apple Inc.\n0000320193,AAPL,Apple Inc.\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate CIK"):
        load_issuers(issuer_file)


def test_ingest_issuer_writes_raw_data_and_metadata(tmp_path: Path) -> None:
    issuer = Issuer(cik="320193", ticker="AAPL", name="Apple Inc.")
    response_data = {"cik": 320193, "entityName": "Apple Inc.", "facts": {}}

    def fetcher(cik: str, user_agent: str) -> tuple[dict, int, str]:
        assert cik == "0000320193"
        assert user_agent == "test contact@example.com"
        return response_data, 200, "https://data.sec.gov/example.json"

    result = ingest_issuer(issuer, tmp_path, "test contact@example.com", fetcher)
    data_path, metadata_path = companyfacts_paths(tmp_path, issuer.cik)

    assert result.status == "downloaded"
    assert json.loads(data_path.read_text(encoding="utf-8")) == response_data
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["cik"] == "0000320193"
    assert metadata["ticker"] == "AAPL"
    assert metadata["entity_name"] == "Apple Inc."
    assert metadata["source_url"] == "https://data.sec.gov/example.json"
    assert metadata["http_status"] == 200
    assert "contact@example.com" not in metadata_path.read_text(encoding="utf-8")


def test_ingest_issuer_uses_complete_cache(tmp_path: Path) -> None:
    issuer = Issuer(cik="0000320193", ticker="AAPL", name="Apple Inc.")
    data_path, metadata_path = companyfacts_paths(tmp_path, issuer.cik)
    data_path.parent.mkdir(parents=True)
    data_path.write_text("{}", encoding="utf-8")
    metadata_path.write_text("{}", encoding="utf-8")

    def unexpected_fetch(cik: str, user_agent: str) -> tuple[dict, int, str]:
        raise AssertionError("complete cache should not make a request")

    result = ingest_issuer(
        issuer, tmp_path, "test contact@example.com", unexpected_fetch
    )

    assert result.status == "cached"


def test_ingest_issuers_delays_only_after_requests(tmp_path: Path) -> None:
    first_download = Issuer(cik="320193", ticker="AAPL", name="Apple Inc.")
    cached = Issuer(cik="789019", ticker="MSFT", name="Microsoft Corporation")
    last_download = Issuer(cik="1018724", ticker="AMZN", name="Amazon.com Inc.")
    cached_paths = companyfacts_paths(tmp_path, cached.cik)
    cached_paths[0].parent.mkdir(parents=True)
    cached_paths[0].write_text("{}", encoding="utf-8")
    cached_paths[1].write_text("{}", encoding="utf-8")
    delays = []

    def fetcher(cik: str, user_agent: str) -> tuple[dict, int, str]:
        return {"entityName": "Example Corp"}, 200, "https://example.com"

    results = ingest_issuers(
        [first_download, cached, last_download],
        tmp_path,
        "test contact@example.com",
        fetcher=fetcher,
        sleeper=delays.append,
    )

    assert [result.status for result in results] == [
        "downloaded",
        "cached",
        "downloaded",
    ]
    assert delays == [0.25]


def test_failed_request_is_reported(tmp_path: Path) -> None:
    issuer = Issuer(cik="320193", ticker="AAPL", name="Apple Inc.")

    def failed_fetch(cik: str, user_agent: str) -> tuple[dict, int, str]:
        raise requests.Timeout("request timed out")

    result = ingest_issuer(
        issuer, tmp_path / "raw", "test contact@example.com", failed_fetch
    )
    report_path = tmp_path / "reports" / "failures.csv"
    write_failure_report([result], report_path)

    assert result.status == "failed"
    assert "Timeout" in (result.error or "")
    assert "AAPL" in report_path.read_text(encoding="utf-8")
