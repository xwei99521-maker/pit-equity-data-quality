import pytest

from pit_equity.sec_client import (
    companyfacts_url,
    normalize_cik,
    summarize_companyfacts,
)


def test_normalize_cik_adds_leading_zeroes() -> None:
    assert normalize_cik("320193") == "0000320193"
    assert normalize_cik("CIK0000320193") == "0000320193"


@pytest.mark.parametrize("cik", ["", "AAPL", "12345678901"])
def test_normalize_cik_rejects_invalid_values(cik: str) -> None:
    with pytest.raises(ValueError):
        normalize_cik(cik)


def test_companyfacts_url_uses_normalized_cik() -> None:
    assert companyfacts_url("320193") == (
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"
    )


def test_summarize_companyfacts_counts_concepts_and_observations() -> None:
    data = {
        "cik": 320193,
        "entityName": "Example Corp",
        "facts": {
            "us-gaap": {
                "Assets": {"units": {"USD": [{"val": 10}, {"val": 12}]}},
                "NetIncomeLoss": {"units": {"USD": [{"val": 2}]}},
            },
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {"shares": [{"val": 5}]}
                }
            },
        },
    }

    assert summarize_companyfacts(data) == {
        "entity_name": "Example Corp",
        "cik": "320193",
        "taxonomy_count": 2,
        "concept_count": 3,
        "observation_count": 4,
    }
