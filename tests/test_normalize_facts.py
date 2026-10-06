import csv
import json
from datetime import date
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from pit_equity.ingest_sec import Issuer, companyfacts_paths
from pit_equity.normalize_facts import (
    ConceptRule,
    build_facts,
    load_concept_rules,
    normalize_companyfacts,
)

RULES = [
    ConceptRule("assets", "us-gaap", "Assets", "instant", "USD"),
    ConceptRule(
        "revenue",
        "us-gaap",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "duration",
        "USD",
    ),
]


def companyfacts_fixture() -> dict:
    return {
        "cik": 320193,
        "entityName": "Apple Inc.",
        "facts": {
            "us-gaap": {
                "Assets": {
                    "label": "Assets",
                    "units": {
                        "USD": [
                            {
                                "end": "2023-09-30",
                                "val": 352583000000,
                                "accn": "0000320193-23-000106",
                                "fy": 2023,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2023-11-03",
                                "frame": "CY2023Q3I",
                            }
                        ]
                    },
                },
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "label": "Revenue",
                    "units": {
                        "USD": [
                            {
                                "start": "2022-09-25",
                                "end": "2023-09-30",
                                "val": 383285000000,
                                "accn": "0000320193-23-000106",
                                "fy": 2023,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2023-11-03",
                            }
                        ]
                    },
                },
            }
        },
    }


def test_normalizes_instant_and_duration_facts_with_lineage() -> None:
    issuer = Issuer(cik="0000320193", ticker="AAPL", name="Apple Inc.")

    rows = normalize_companyfacts(issuer, companyfacts_fixture(), RULES)

    assert len(rows) == 2
    assets = next(row for row in rows if row["canonical_concept"] == "assets")
    revenue = next(row for row in rows if row["canonical_concept"] == "revenue")
    assert assets["start_date"] is None
    assert assets["end_date"] == date(2023, 9, 30)
    assert assets["unit"] == "USD"
    assert assets["accession"] == "0000320193-23-000106"
    assert revenue["start_date"] == date(2022, 9, 25)
    assert revenue["filed_date"] == date(2023, 11, 3)
    assert revenue["tag"] == "RevenueFromContractWithCustomerExcludingAssessedTax"


def test_rejects_duration_fact_without_start_date() -> None:
    issuer = Issuer(cik="0000320193", ticker="AAPL", name="Apple Inc.")
    data = companyfacts_fixture()
    observation = data["facts"]["us-gaap"][
        "RevenueFromContractWithCustomerExcludingAssessedTax"
    ]["units"]["USD"][0]
    del observation["start"]

    with pytest.raises(ValueError, match="missing start"):
        normalize_companyfacts(issuer, data, RULES)


def test_rejects_response_for_different_cik() -> None:
    issuer = Issuer(cik="0000320193", ticker="AAPL", name="Apple Inc.")
    data = companyfacts_fixture()
    data["cik"] = 789019

    with pytest.raises(ValueError, match="does not match"):
        normalize_companyfacts(issuer, data, RULES)


def test_load_concept_rules_rejects_conflicting_aliases(tmp_path: Path) -> None:
    path = tmp_path / "concepts.csv"
    path.write_text(
        "canonical_concept,taxonomy,tag,period_type,expected_unit\n"
        "revenue,us-gaap,Revenues,duration,USD\n"
        "revenue,us-gaap,OtherRevenue,instant,USD\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="share a definition"):
        load_concept_rules(path)


def test_build_facts_writes_parquet_and_coverage_report(tmp_path: Path) -> None:
    issuer_path = tmp_path / "issuers.csv"
    issuer_path.write_text(
        "cik,ticker,name\n320193,AAPL,Apple Inc.\n", encoding="utf-8"
    )
    concept_path = tmp_path / "concepts.csv"
    concept_path.write_text(
        "canonical_concept,taxonomy,tag,period_type,expected_unit\n"
        "assets,us-gaap,Assets,instant,USD\n"
        "liabilities,us-gaap,Liabilities,instant,USD\n",
        encoding="utf-8",
    )
    raw_dir = tmp_path / "raw"
    data_path, _ = companyfacts_paths(raw_dir, "320193")
    data_path.parent.mkdir(parents=True)
    data = companyfacts_fixture()
    unexpected_unit = data["facts"]["us-gaap"]["Assets"]["units"]["USD"][0].copy()
    unexpected_unit["val"] = 100
    data["facts"]["us-gaap"]["Assets"]["units"]["shares"] = [unexpected_unit]
    data_path.write_text(json.dumps(data), encoding="utf-8")
    output_path = tmp_path / "processed" / "facts.parquet"
    coverage_path = tmp_path / "reports" / "coverage.csv"

    summary = build_facts(
        issuer_path, concept_path, raw_dir, output_path, coverage_path
    )

    table = pq.read_table(output_path)
    assert summary.row_count == 2
    assert summary.covered_pairs == 1
    assert summary.total_pairs == 2
    assert summary.unit_anomalies == ("assets=shares",)
    assert table.column("canonical_concept").to_pylist() == ["assets", "assets"]
    assert set(table.column("unit").to_pylist()) == {"USD", "shares"}
    with coverage_path.open(newline="", encoding="utf-8") as file:
        coverage = list(csv.DictReader(file))
    assert [row["status"] for row in coverage] == ["covered", "missing"]
