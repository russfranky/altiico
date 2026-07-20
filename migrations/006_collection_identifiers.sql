-- Migration 006: collection_identifiers
--
-- A contract address is NOT a unique collection identifier. Multiple OpenSea
-- collections (pixelbeasts, chametheon, cyberanimedoll-avatar) share the same
-- shared storefront ERC-1155 contract 0x495f947276749ce646f68ac8c248420045cb7b5e.
-- This table is a multi-identifier registry mapping a collection to any number
-- of external identifiers across namespaces.

CREATE TABLE IF NOT EXISTS collection_identifiers (
    collection_id     TEXT    NOT NULL,
    namespace         TEXT    NOT NULL,   -- opensea_slug, contract_token, reservoir_id, nftscan_id, metaplex_mint, a3ac_row
    value             TEXT    NOT NULL,
    chain             TEXT,
    contract          TEXT,
    token_id          TEXT,
    verified_at       TEXT,               -- ISO 8601 timestamp
    resolution_source TEXT,               -- opensea-token, opensea-slug, manual, reservoir, a3ac, legacy
    PRIMARY KEY (collection_id, namespace, value),
    FOREIGN KEY (collection_id) REFERENCES collections(id)
);

CREATE INDEX IF NOT EXISTS idx_ci_contract_token
    ON collection_identifiers(chain, contract, token_id);

CREATE INDEX IF NOT EXISTS idx_ci_namespace_value
    ON collection_identifiers(namespace, value);

-- Backfill opensea_slug rows from the collections table.
INSERT OR IGNORE INTO collection_identifiers
    (collection_id, namespace, value, chain, contract, verified_at, resolution_source)
SELECT
    id,
    'opensea_slug',
    opensea_slug,
    chain,
    contract,
    strftime('%Y-%m-%dT%H:%M:%SZ', 'now'),
    'legacy'
FROM collections
WHERE opensea_slug IS NOT NULL;

-- Backfill contract_token rows from the contracts table.
INSERT OR IGNORE INTO collection_identifiers
    (collection_id, namespace, value, chain, contract, verified_at, resolution_source)
SELECT
    collection_id,
    'contract_token',
    address,
    chain,
    address,
    strftime('%Y-%m-%dT%H:%M:%SZ', 'now'),
    'legacy'
FROM contracts;
