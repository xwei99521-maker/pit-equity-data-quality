import argparse
from collections import Counter
from pathlib import Path

from pit_equity.config import sec_user_agent
from pit_equity.ingest_sec import ingest_issuers, load_issuers, write_failure_report
from pit_equity.normalize_facts import FACT_SCHEMA, build_facts
from pit_equity.sec_client import fetch_companyfacts, summarize_companyfacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pit_equity",
        description="Inspect point-in-time equity data sources.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    inspect_sec = commands.add_parser(
        "inspect-sec", help="summarize one SEC Company Facts response"
    )
    inspect_sec.add_argument("--cik", required=True, help="SEC central index key")

    ingest_sec = commands.add_parser(
        "ingest-sec", help="download and cache SEC Company Facts data"
    )
    ingest_sec.add_argument("--issuers", type=Path, default=Path("config/issuers.csv"))
    ingest_sec.add_argument("--raw-dir", type=Path, default=Path("data/raw/sec"))
    ingest_sec.add_argument(
        "--failure-report",
        type=Path,
        default=Path("reports/generated/sec_ingest_failures.csv"),
    )

    build_facts_parser = commands.add_parser(
        "build-facts", help="normalize cached SEC Company Facts data"
    )
    build_facts_parser.add_argument(
        "--issuers", type=Path, default=Path("config/issuers.csv")
    )
    build_facts_parser.add_argument(
        "--concepts", type=Path, default=Path("config/concepts.csv")
    )
    build_facts_parser.add_argument(
        "--raw-dir", type=Path, default=Path("data/raw/sec")
    )
    build_facts_parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/sec/facts.parquet"),
    )
    build_facts_parser.add_argument(
        "--coverage-report",
        type=Path,
        default=Path("reports/generated/concept_coverage.csv"),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.command == "inspect-sec":
        data = fetch_companyfacts(args.cik, sec_user_agent())
        summary = summarize_companyfacts(data)
        print(f"Entity: {summary['entity_name']}")
        print(f"CIK: {summary['cik']}")
        print(f"Taxonomies: {summary['taxonomy_count']}")
        print(f"Concepts: {summary['concept_count']}")
        print(f"Fact observations: {summary['observation_count']}")

    if args.command == "ingest-sec":
        issuers = load_issuers(args.issuers)
        results = ingest_issuers(issuers, args.raw_dir, sec_user_agent())
        write_failure_report(results, args.failure_report)
        counts = Counter(result.status for result in results)

        print(f"Issuers: {len(results)}")
        print(f"Downloaded: {counts['downloaded']}")
        print(f"Cached: {counts['cached']}")
        print(f"Failed: {counts['failed']}")
        for result in results:
            if result.status == "failed":
                print(f"Failure {result.issuer.ticker}: {result.error}")

        if counts["failed"]:
            raise SystemExit(1)

    if args.command == "build-facts":
        summary = build_facts(
            args.issuers,
            args.concepts,
            args.raw_dir,
            args.output,
            args.coverage_report,
        )
        print("Schema:")
        for field in FACT_SCHEMA:
            print(f"  {field.name}: {field.type}")
        print(f"Rows: {summary.row_count}")
        print(f"Issuers: {summary.issuer_count}")
        print(f"Canonical concepts: {summary.concept_count}")
        print(f"Issuer-concept coverage: {summary.covered_pairs}/{summary.total_pairs}")
        print(f"Output: {summary.output_path}")
        print(f"Coverage report: {summary.coverage_path}")
        if summary.unit_anomalies:
            print(f"Anomalous units: {', '.join(summary.unit_anomalies)}")
        else:
            print("Anomalous units: none")


if __name__ == "__main__":
    main()
