from typing import Any

import requests

SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


def normalize_cik(cik: str) -> str:
    digits = cik.removeprefix("CIK")
    if not digits.isdigit() or len(digits) > 10:
        raise ValueError("CIK must contain at most ten digits")
    return digits.zfill(10)


def companyfacts_url(cik: str) -> str:
    return SEC_COMPANYFACTS_URL.format(cik=normalize_cik(cik))


def fetch_companyfacts(cik: str, user_agent: str) -> dict[str, Any]:
    response = requests.get(
        companyfacts_url(cik),
        headers={
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def summarize_companyfacts(data: dict[str, Any]) -> dict[str, int | str]:
    facts = data.get("facts", {})
    concept_count = 0
    observation_count = 0

    for taxonomy in facts.values():
        concept_count += len(taxonomy)
        for concept in taxonomy.values():
            observation_count += sum(
                len(observations) for observations in concept.get("units", {}).values()
            )

    return {
        "entity_name": data.get("entityName", "Unknown"),
        "cik": str(data.get("cik", "Unknown")),
        "taxonomy_count": len(facts),
        "concept_count": concept_count,
        "observation_count": observation_count,
    }
