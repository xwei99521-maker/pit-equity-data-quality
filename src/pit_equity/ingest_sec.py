import csv
import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from pit_equity.sec_client import normalize_cik, request_companyfacts

CompanyFactsFetcher = Callable[[str, str], tuple[dict[str, Any], int, str]]


@dataclass(frozen=True)
class Issuer:
    cik: str
    ticker: str
    name: str


@dataclass(frozen=True)
class IngestResult:
    issuer: Issuer
    status: str
    error: str | None = None


def load_issuers(path: Path) -> list[Issuer]:
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        required_columns = {"cik", "ticker", "name"}
        if not reader.fieldnames or not required_columns.issubset(reader.fieldnames):
            raise ValueError("issuer file must contain cik, ticker, and name columns")

        issuers = [
            Issuer(
                cik=normalize_cik(row["cik"].strip()),
                ticker=row["ticker"].strip(),
                name=row["name"].strip(),
            )
            for row in reader
        ]

    ciks = [issuer.cik for issuer in issuers]
    if len(ciks) != len(set(ciks)):
        raise ValueError("issuer file contains duplicate CIK values")
    return issuers


def companyfacts_paths(raw_dir: Path, cik: str) -> tuple[Path, Path]:
    stem = f"CIK{normalize_cik(cik)}"
    companyfacts_dir = raw_dir / "companyfacts"
    return (
        companyfacts_dir / f"{stem}.json",
        companyfacts_dir / f"{stem}.metadata.json",
    )


def _write_json(path: Path, data: dict[str, Any], *, indent: int | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=indent, separators=None if indent else (",", ":"))
        file.write("\n")
    os.replace(temporary_path, path)


def ingest_issuer(
    issuer: Issuer,
    raw_dir: Path,
    user_agent: str,
    fetcher: CompanyFactsFetcher = request_companyfacts,
) -> IngestResult:
    normalized_cik = normalize_cik(issuer.cik)
    data_path, metadata_path = companyfacts_paths(raw_dir, normalized_cik)
    if data_path.exists() and metadata_path.exists():
        return IngestResult(issuer=issuer, status="cached")

    try:
        data, http_status, source_url = fetcher(normalized_cik, user_agent)
        _write_json(data_path, data, indent=None)
        _write_json(
            metadata_path,
            {
                "cik": normalized_cik,
                "ticker": issuer.ticker,
                "configured_name": issuer.name,
                "entity_name": data.get("entityName"),
                "source_url": source_url,
                "http_status": http_status,
                "fetched_at": datetime.now(UTC).isoformat(),
            },
            indent=2,
        )
    except (OSError, ValueError, requests.RequestException) as error:
        return IngestResult(
            issuer=issuer,
            status="failed",
            error=f"{type(error).__name__}: {error}",
        )

    return IngestResult(issuer=issuer, status="downloaded")


def ingest_issuers(
    issuers: list[Issuer],
    raw_dir: Path,
    user_agent: str,
    *,
    delay_seconds: float = 0.25,
    fetcher: CompanyFactsFetcher = request_companyfacts,
    sleeper: Callable[[float], None] = time.sleep,
) -> list[IngestResult]:
    results = []
    for index, issuer in enumerate(issuers):
        result = ingest_issuer(issuer, raw_dir, user_agent, fetcher)
        results.append(result)

        made_request = result.status != "cached"
        has_next_issuer = index < len(issuers) - 1
        if made_request and has_next_issuer:
            sleeper(delay_seconds)

    return results


def write_failure_report(results: list[IngestResult], path: Path) -> None:
    failures = [result for result in results if result.status == "failed"]
    if not failures:
        if path.exists():
            path.unlink()
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["cik", "ticker", "error"])
        writer.writeheader()
        for result in failures:
            writer.writerow(
                {
                    "cik": result.issuer.cik,
                    "ticker": result.issuer.ticker,
                    "error": result.error,
                }
            )
