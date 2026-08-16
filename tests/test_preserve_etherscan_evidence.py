from scripts.audit_etherscan_authority import is_optional_explorer_error
from scripts.preserve_etherscan_evidence import merge_with_previous, refresh_unusable


def report(collection):
    return {
        "summary": {
            "collectionsInspected": 1,
            "collectionsWithErrors": int(bool(collection.get("errors"))),
        },
        "collections": [collection],
    }


def test_rate_limited_missing_evidence_preserves_previous_corroboration():
    previous = report(
        {
            "catalogId": "demo",
            "chain": "ethereum",
            "contract": "0xabc",
            "observedAt": "old",
            "errors": [],
            "contractEvidence": {
                "creator": "0xcreator",
                "verifiedSource": True,
                "abiSignals": {"tokenURI": True},
            },
        }
    )
    fresh = report(
        {
            "catalogId": "demo",
            "chain": "ethereum",
            "contract": "0xabc",
            "observedAt": "new",
            "errors": [
                "source: RuntimeError: Etherscan API error: Max calls per sec rate limit reached (3/sec)"
            ],
            "contractEvidence": {
                "creator": None,
                "verifiedSource": False,
                "abiSignals": {},
            },
        }
    )

    merged, preserved = merge_with_previous(fresh, previous)

    item = merged["collections"][0]
    assert preserved == 1
    assert item["contractEvidence"]["creator"] == "0xcreator"
    assert item["evidencePreservation"]["mode"] == "previous_last_good"
    assert merged["summary"]["preservedCollections"] == 1


def test_non_throttled_empty_evidence_is_not_masked():
    previous = report(
        {
            "catalogId": "demo",
            "chain": "ethereum",
            "contract": "0xabc",
            "contractEvidence": {"creator": "0xcreator"},
        }
    )
    fresh = report(
        {
            "catalogId": "demo",
            "chain": "ethereum",
            "contract": "0xabc",
            "errors": [],
            "contractEvidence": {"creator": None},
        }
    )

    merged, preserved = merge_with_previous(fresh, previous)

    assert preserved == 0
    assert merged["collections"][0]["contractEvidence"]["creator"] is None


def test_identity_change_never_reuses_previous_evidence():
    previous = report(
        {
            "catalogId": "demo",
            "chain": "ethereum",
            "contract": "0xold",
            "contractEvidence": {"creator": "0xcreator"},
        }
    )
    fresh = report(
        {
            "catalogId": "demo",
            "chain": "ethereum",
            "contract": "0xnew",
            "errors": ["rate limit reached"],
            "contractEvidence": {},
        }
    )

    merged, preserved = merge_with_previous(fresh, previous)

    assert preserved == 0
    assert merged["collections"][0]["contractEvidence"] == {}


def test_all_error_audit_with_corroboration_remains_usable():
    assert refresh_unusable(66, 66, 62) is False


def test_all_error_audit_without_corroboration_fails_closed():
    assert refresh_unusable(66, 66, 0) is True


def test_etherscan_pro_tokeninfo_is_optional_warning():
    assert is_optional_explorer_error(
        "token_info: RuntimeError: Etherscan API error: Sorry, it looks like you are trying to access an API Pro endpoint. Contact us to upgrade to API Pro."
    )
    assert is_optional_explorer_error(
        "creation: RuntimeError: Etherscan API error: Free API access is not supported for this chain"
    )
    assert not is_optional_explorer_error(
        "source: RuntimeError: Etherscan API error: Invalid API Key"
    )
