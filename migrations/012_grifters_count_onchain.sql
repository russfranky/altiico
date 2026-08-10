-- 012_grifters_count_onchain.sql
--
-- Canonical count correction: Grifters Squaddies (grifterssquaddies).
-- Verified on-chain 2026-08-09 against the Base contract
-- 0xa94c652c16525e6b7cac82a34eab18b5174ad23c (name "Grifters Squaddies",
-- symbol GRFT): totalSupply() = 1453. The prior avatar_count (812) was a
-- stale/partial index; the reported ~4,200 did not verify on-chain.
--
-- The claim/bridge contract 0xc1374b803dfb1a9c87eab9e76929222dba3a8c39 is a
-- DIFFERENT contract (name "Nifty Island Creations", symbol NI-CREATE) and is
-- deliberately NOT recorded as the Grifters contract.
--
-- Apply:  sqlite3 data/vrm_index.db < migrations/012_grifters_count_onchain.sql

UPDATE collections
SET avatar_count      = 1453,
    total_supply      = 1453,
    max_supply        = 1453,
    max_supply_source = 'onchain:base:0xa94c652c:totalSupply@2026-08-09'
WHERE id = 'grifterssquaddies';
