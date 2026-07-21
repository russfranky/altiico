-- Migration 009: chain-neutral CAIP identifiers
--
-- The original schema assumed EVM-style chains: a free-text `chain` column
-- (ethereum, polygon, base, ...) and hex contract addresses. To support
-- non-EVM chains (Solana, Tezos, Flow, Sui, Aptos, Bitcoin) we adopt CAIP-2
-- (chain namespace + reference) and CAIP-19 (asset namespace) identifiers
-- alongside the legacy columns.
--
-- New columns are additive and NULL/'eip155' by default so existing queries
-- keep working. The legacy `chain` and `contract` columns are retained for
-- backward compatibility; the CAIP columns are the authoritative cross-chain
-- key going forward.
--
-- CAIP-2 namespaces:  eip155, solana, tezos, flow, sui, aptos, bitcoin, arweave
-- CAIP-2 references:  eip155 chain id (1, 137, 8453, ...), solana 'mainnet-beta', etc.
-- CAIP-19 asset namespaces: erc721, erc1155, metaplex, fa2, ...

-- ---------------------------------------------------------------------------
-- collection_identifiers
-- ---------------------------------------------------------------------------

ALTER TABLE collection_identifiers ADD COLUMN chain_namespace TEXT DEFAULT 'eip155';
ALTER TABLE collection_identifiers ADD COLUMN chain_reference TEXT DEFAULT NULL;
ALTER TABLE collection_identifiers ADD COLUMN asset_namespace TEXT DEFAULT NULL;

-- Backfill chain_namespace / chain_reference from the legacy chain column.
UPDATE collection_identifiers
SET chain_namespace = 'eip155',
    chain_reference = CASE chain
        WHEN 'ethereum'  THEN '1'
        WHEN 'polygon'   THEN '137'
        WHEN 'base'      THEN '8453'
        WHEN 'optimism'  THEN '10'
        WHEN 'shape'     THEN '360'
        WHEN 'arbitrum'  THEN '42161'
        WHEN 'sepolia'   THEN '11155111'
        WHEN 'ape_chain' THEN '33139'
        ELSE NULL
    END
WHERE chain IN ('ethereum','polygon','base','optimism','shape','arbitrum','sepolia','ape_chain');

UPDATE collection_identifiers
SET chain_namespace = 'solana',
    chain_reference = 'mainnet-beta'
WHERE chain = 'solana';

UPDATE collection_identifiers
SET chain_namespace = 'arweave',
    chain_reference = 'arweave.mainnet'
WHERE chain = 'arweave';

-- multi or NULL: safe default for existing EVM-centric data.
UPDATE collection_identifiers
SET chain_namespace = 'eip155'
WHERE chain_namespace IS NULL
   OR chain IN ('multi');

-- Cross-chain lookup index.
CREATE INDEX IF NOT EXISTS idx_ci_chain_ns
    ON collection_identifiers(chain_namespace, chain_reference);

-- ---------------------------------------------------------------------------
-- collections
-- ---------------------------------------------------------------------------

ALTER TABLE collections ADD COLUMN chain_namespace TEXT DEFAULT 'eip155';
ALTER TABLE collections ADD COLUMN chain_reference TEXT DEFAULT NULL;

UPDATE collections
SET chain_namespace = 'eip155',
    chain_reference = CASE chain
        WHEN 'ethereum'  THEN '1'
        WHEN 'polygon'   THEN '137'
        WHEN 'base'      THEN '8453'
        WHEN 'optimism'  THEN '10'
        WHEN 'shape'     THEN '360'
        WHEN 'arbitrum'  THEN '42161'
        WHEN 'sepolia'   THEN '11155111'
        WHEN 'ape_chain' THEN '33139'
        ELSE NULL
    END
WHERE chain IN ('ethereum','polygon','base','optimism','shape','arbitrum','sepolia','ape_chain');

UPDATE collections
SET chain_namespace = 'solana',
    chain_reference = 'mainnet-beta'
WHERE chain = 'solana';

UPDATE collections
SET chain_namespace = 'arweave',
    chain_reference = 'arweave.mainnet'
WHERE chain = 'arweave';

UPDATE collections
SET chain_namespace = 'eip155'
WHERE chain_namespace IS NULL
   OR chain IN ('multi');
