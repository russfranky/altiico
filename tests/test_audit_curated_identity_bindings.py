from scripts import audit_curated_identity_bindings as audit


def collection(
    *,
    cid="catalog-row",
    name="Catalog Row",
    contract="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    metadata="https://example.test/meta/1",
    contracts=None,
):
    return {
        "id": cid,
        "name": name,
        "contract": contract,
        "sample_metadata_url": metadata,
        "contracts": contracts or [{"address": contract, "chain": "ethereum", "is_primary": 1}],
        "vrm_param": "vrm_url",
        "vrm_url_https": "https://example.test/avatar.vrm",
        "vrm_check_status": "timeout",
    }


def registry_row(
    *,
    name="Registry Collection",
    contract="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    metadata="https://example.test/meta/1",
):
    return {
        "registryName": name,
        "contract": contract,
        "metadataUrl": metadata,
        "metadataParam": "VRM: `vrm_url`",
    }


def test_exact_metadata_url_with_different_contract_is_flagged():
    payload = audit.audit_bindings([registry_row()], [collection()])

    assert payload["summary"]["identityMismatchFindings"] == 1
    finding = payload["findings"][0]
    assert finding["type"] == "exact_metadata_url_bound_to_different_contract"
    assert finding["registryContract"] == "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    assert finding["catalogPrimaryContract"] == "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert finding["catalogId"] == "catalog-row"


def test_same_contract_is_not_flagged():
    contract = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    payload = audit.audit_bindings(
        [registry_row(contract=contract)],
        [collection(contract=contract)],
    )

    assert payload["summary"]["identityMismatchFindings"] == 0
    assert payload["findings"] == []


def test_secondary_known_contract_prevents_false_positive():
    registry_contract = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    payload = audit.audit_bindings(
        [registry_row(contract=registry_contract)],
        [
            collection(
                contracts=[
                    {
                        "address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                        "chain": "ethereum",
                        "is_primary": 1,
                    },
                    {
                        "address": registry_contract,
                        "chain": "ethereum",
                        "is_primary": 0,
                    },
                ]
            )
        ],
    )

    assert payload["summary"]["identityMismatchFindings"] == 0


def test_url_normalization_allows_only_syntactic_equivalence():
    row = registry_row(metadata="HTTPS://EXAMPLE.TEST/meta/1/")
    payload = audit.audit_bindings(
        [row],
        [collection(metadata="https://example.test/meta/1")],
    )
    assert payload["summary"]["identityMismatchFindings"] == 1

    unrelated = audit.audit_bindings(
        [registry_row(metadata="https://example.test/meta/2")],
        [collection(metadata="https://example.test/meta/1")],
    )
    assert unrelated["summary"]["identityMismatchFindings"] == 0


def test_same_host_or_name_without_exact_metadata_url_is_not_evidence():
    payload = audit.audit_bindings(
        [
            registry_row(
                name="Same Project",
                metadata="https://example.test/registry/1",
            )
        ],
        [
            collection(
                name="Same Project",
                metadata="https://example.test/catalog/1",
            )
        ],
    )

    assert payload["summary"]["registryRowsWithCatalogMetadataMatch"] == 0
    assert payload["findings"] == []


def test_registry_contract_catalog_ids_are_reported_for_manual_reconciliation():
    registry_contract = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    payload = audit.audit_bindings(
        [registry_row(contract=registry_contract)],
        [
            collection(cid="wrong-binding"),
            collection(
                cid="exact-contract-row",
                contract=registry_contract,
                metadata="https://other.example/meta/9",
            ),
        ],
    )

    assert payload["summary"]["identityMismatchFindings"] == 1
    assert payload["findings"][0]["registryContractCatalogIds"] == ["exact-contract-row"]
