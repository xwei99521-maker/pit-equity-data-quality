import csv
import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from pit_equity.ingest_sec import Issuer, companyfacts_paths, load_issuers
from pit_equity.sec_client import normalize_cik

FACT_SCHEMA = pa.schema(
    [
        pa.field("cik", pa.string(), nullable=False),
        pa.field("ticker", pa.string(), nullable=False),
        pa.field("entity_name", pa.string(), nullable=False),
        pa.field("canonical_concept", pa.string(), nullable=False),
        pa.field("period_type", pa.string(), nullable=False),
        pa.field("taxonomy", pa.string(), nullable=False),
        pa.field("tag", pa.string(), nullable=False),
        pa.field("label", pa.string(), nullable=False),
        pa.field("unit", pa.string(), nullable=False),
        pa.field("value", pa.int64(), nullable=False),
        pa.field("start_date", pa.date32()),
        pa.field("end_date", pa.date32(), nullable=False),
        pa.field("filed_date", pa.date32(), nullable=False),
        pa.field("accession", pa.string(), nullable=False),
        pa.field("form", pa.string(), nullable=False),
        pa.field("fiscal_year", pa.int32()),
        pa.field("fiscal_period", pa.string()),
        pa.field("frame", pa.string()),
    ]
)


@dataclass(frozen=True)
class ConceptRule:
    canonical_concept: str
    taxonomy: str
    tag: str
    period_type: str
    expected_unit: str


@dataclass(frozen=True)
class BuildFactsSummary:
    output_path: Path
    coverage_path: Path
    row_count: int
    issuer_count: int
    concept_count: int
    covered_pairs: int
    total_pairs: int
    unit_anomalies: tuple[str, ...]


def load_concept_rules(path: Path) -> list[ConceptRule]:
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        required_columns = {
            "canonical_concept",
            "taxonomy",
            "tag",
            "period_type",
            "expected_unit",
        }
        if not reader.fieldnames or not required_columns.issubset(reader.fieldnames):
            raise ValueError("concept file is missing required columns")

        rules = [
            ConceptRule(
                canonical_concept=row["canonical_concept"].strip(),
                taxonomy=row["taxonomy"].strip(),
                tag=row["tag"].strip(),
                period_type=row["period_type"].strip(),
                expected_unit=row["expected_unit"].strip(),
            )
            for row in reader
        ]

    if not rules:
        raise ValueError("concept file must contain at least one mapping")
    source_keys = [(rule.taxonomy, rule.tag) for rule in rules]
    if len(source_keys) != len(set(source_keys)):
        raise ValueError("concept file contains duplicate taxonomy and tag pairs")
    if any(rule.period_type not in {"instant", "duration"} for rule in rules):
        raise ValueError("period_type must be instant or duration")
    if any(not all(vars(rule).values()) for rule in rules):
        raise ValueError("concept mapping values cannot be blank")

    definitions: dict[str, tuple[str, str]] = {}
    for rule in rules:
        definition = (rule.period_type, rule.expected_unit)
        previous = definitions.setdefault(rule.canonical_concept, definition)
        if previous != definition:
            raise ValueError(
                "aliases for one canonical concept must share a definition"
            )
    return rules


def _required_text(observation: dict[str, Any], key: str, context: str) -> str:
    value = observation.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context} is missing {key}")
    return value


def _date_value(
    observation: dict[str, Any], key: str, context: str, *, required: bool
) -> date | None:
    value = observation.get(key)
    if value is None:
        if not required:
            return None
        raise ValueError(f"{context} is missing {key}")
    if not isinstance(value, str):
        raise TypeError(f"{context} has non-text {key}")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{context} has invalid {key}: {value}") from error


def _integer_value(observation: dict[str, Any], context: str) -> int:
    value = observation.get("val")
    if isinstance(value, bool):
        raise TypeError(f"{context} has a non-numeric value")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise ValueError(f"{context} does not contain a whole-number value")


def normalize_companyfacts(
    issuer: Issuer, data: dict[str, Any], rules: list[ConceptRule]
) -> list[dict[str, Any]]:
    response_cik = normalize_cik(str(data.get("cik", "")))
    if response_cik != issuer.cik:
        raise ValueError(f"response CIK {response_cik} does not match {issuer.cik}")

    entity_name = data.get("entityName")
    if not isinstance(entity_name, str) or not entity_name:
        raise ValueError(f"{issuer.ticker} response is missing entityName")

    facts = data.get("facts")
    if facts is None:
        raise ValueError(f"{issuer.ticker} response is missing facts")
    if not isinstance(facts, dict):
        raise TypeError(f"{issuer.ticker} facts must be an object")

    rows = []
    for rule in rules:
        concept = facts.get(rule.taxonomy, {}).get(rule.tag)
        if concept is None:
            continue
        if not isinstance(concept, dict):
            raise TypeError(f"{issuer.ticker} {rule.tag} must be an object")

        label = concept.get("label")
        units = concept.get("units")
        if label is None or units is None:
            raise ValueError(f"{issuer.ticker} {rule.tag} is missing concept metadata")
        if not isinstance(label, str) or not isinstance(units, dict):
            raise TypeError(f"{issuer.ticker} {rule.tag} has invalid concept metadata")

        for unit, observations in units.items():
            if not isinstance(observations, list):
                raise TypeError(f"{issuer.ticker} {rule.tag} has invalid observations")
            for observation in observations:
                context = f"{issuer.ticker} {rule.taxonomy}:{rule.tag}"
                start_date = _date_value(
                    observation,
                    "start",
                    context,
                    required=rule.period_type == "duration",
                )
                if rule.period_type == "instant" and start_date is not None:
                    raise ValueError(f"{context} instant fact contains a start date")

                fiscal_year = observation.get("fy")
                rows.append(
                    {
                        "cik": issuer.cik,
                        "ticker": issuer.ticker,
                        "entity_name": entity_name,
                        "canonical_concept": rule.canonical_concept,
                        "period_type": rule.period_type,
                        "taxonomy": rule.taxonomy,
                        "tag": rule.tag,
                        "label": label,
                        "unit": unit,
                        "value": _integer_value(observation, context),
                        "start_date": start_date,
                        "end_date": _date_value(
                            observation, "end", context, required=True
                        ),
                        "filed_date": _date_value(
                            observation, "filed", context, required=True
                        ),
                        "accession": _required_text(observation, "accn", context),
                        "form": _required_text(observation, "form", context),
                        "fiscal_year": int(fiscal_year)
                        if fiscal_year is not None
                        else None,
                        "fiscal_period": observation.get("fp"),
                        "frame": observation.get("frame"),
                    }
                )

    return sorted(
        rows,
        key=lambda row: (
            row["ticker"],
            row["canonical_concept"],
            row["end_date"],
            row["filed_date"],
            row["accession"],
            row["tag"],
            row["unit"],
            row["start_date"] or date.min,
        ),
    )


def _coverage_rows(
    issuers: list[Issuer], rules: list[ConceptRule], rows: list[dict[str, Any]]
) -> list[dict[str, str | int]]:
    observed: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        observed.setdefault((row["cik"], row["canonical_concept"]), []).append(row)

    definitions: dict[str, tuple[str, str]] = {}
    for rule in rules:
        definitions.setdefault(
            rule.canonical_concept, (rule.period_type, rule.expected_unit)
        )

    coverage = []
    for issuer in issuers:
        for canonical_concept, (period_type, expected_unit) in definitions.items():
            matches = observed.get((issuer.cik, canonical_concept), [])
            coverage.append(
                {
                    "cik": issuer.cik,
                    "ticker": issuer.ticker,
                    "canonical_concept": canonical_concept,
                    "period_type": period_type,
                    "expected_unit": expected_unit,
                    "status": "covered" if matches else "missing",
                    "observation_count": len(matches),
                    "mapped_tags": "|".join(sorted({row["tag"] for row in matches})),
                    "observed_units": "|".join(
                        sorted({row["unit"] for row in matches})
                    ),
                }
            )
    return coverage


def _write_coverage(path: Path, coverage: list[dict[str, str | int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    with temporary_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(coverage[0]))
        writer.writeheader()
        writer.writerows(coverage)
    os.replace(temporary_path, path)


def _write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    table = pa.Table.from_pylist(rows, schema=FACT_SCHEMA)
    pq.write_table(table, temporary_path, compression="zstd")
    os.replace(temporary_path, path)


def build_facts(
    issuer_path: Path,
    concept_path: Path,
    raw_dir: Path,
    output_path: Path,
    coverage_path: Path,
) -> BuildFactsSummary:
    issuers = load_issuers(issuer_path)
    if not issuers:
        raise ValueError("issuer file must contain at least one issuer")
    rules = load_concept_rules(concept_path)
    rows = []
    for issuer in issuers:
        data_path, _ = companyfacts_paths(raw_dir, issuer.cik)
        with data_path.open(encoding="utf-8") as file:
            data = json.load(file)
        rows.extend(normalize_companyfacts(issuer, data, rules))

    rows.sort(
        key=lambda row: (
            row["ticker"],
            row["canonical_concept"],
            row["end_date"],
            row["filed_date"],
            row["accession"],
            row["tag"],
            row["unit"],
            row["start_date"] or date.min,
        )
    )
    coverage = _coverage_rows(issuers, rules, rows)
    expected_units = {rule.canonical_concept: rule.expected_unit for rule in rules}
    unit_anomalies = tuple(
        sorted(
            {
                f"{row['canonical_concept']}={row['unit']}"
                for row in rows
                if row["unit"] != expected_units[row["canonical_concept"]]
            }
        )
    )

    _write_parquet(output_path, rows)
    _write_coverage(coverage_path, coverage)
    return BuildFactsSummary(
        output_path=output_path,
        coverage_path=coverage_path,
        row_count=len(rows),
        issuer_count=len(issuers),
        concept_count=len(expected_units),
        covered_pairs=sum(row["status"] == "covered" for row in coverage),
        total_pairs=len(coverage),
        unit_anomalies=unit_anomalies,
    )
