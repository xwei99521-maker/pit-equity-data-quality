import argparse

from pit_equity.config import sec_user_agent
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


if __name__ == "__main__":
    main()
