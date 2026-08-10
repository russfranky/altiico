-- 019_dedupe_and_identity.sql
--
-- Fix three identity defects that made the catalog untrustworthy to a reader.
-- Each is verified on-chain; nothing here is inferred from names alone.
--
-- 1. ToxSam carried CryptoAvatars' contract.
--    0xc1def47cf1e15ee8c2a92f4e0e968372880d18d1 reports name "CryptoAvatars",
--    symbol AVNFT, totalSupply 539 (Ethereum, checked 2026-08-10). ToxSam is a
--    separate multi-chain personal collection that merely hosts VRMs via the
--    CryptoAvatars API, so holding that contract created a false duplicate
--    identity between two unrelated rows. Cleared from ToxSam; CryptoAvatars
--    keeps it.
--
-- 2. `vipe-heroes` and `vipe-heroes-genesis` were the same collection split in
--    two: one row held contract 0x3999877754904d8542ad1845d368fa01a5e6e9a5
--    (on-chain "VIPE Heroes", VPH, totalSupply 3000) with no avatars; the other
--    held the 3000 avatar records with no contract, so it failed identity_ok.
--    Survivor: `vipe-heroes-genesis` — it holds the avatars and matches the
--    Hubzz set slug. It absorbs the contract and supply; `vipe-heroes` is
--    dropped.
--
-- 3. `NeonGlitch86-collection` (Ethereum) had no contract, so it could not be
--    resolved on-chain. The Open Source Avatars registry gives it
--    0x776bd31ae5549eac9ed215b5db278229454d5bed. The Shape and Polygon rows are
--    genuinely separate deployments and are left alone.
--
-- NOT treated as duplicates (verified legitimate):
--   * 100avatars-r1/r2/r3 — three distinct Polygonal Mind releases.
--   * The OpenSea shared storefront 0x495f947276749ce646f68ac8c248420045cb7b5e
--     is held by pixelbeasts / chametheon / cyberanimedoll-avatar. That contract
--     is NOT a collection identifier (see AGENTS.md); those are three different
--     collections and must not be merged.
--
-- Apply:  sqlite3 data/vrm_index.db < migrations/019_dedupe_and_identity.sql

-- 1. ToxSam does not own the CryptoAvatars contract.
UPDATE collections SET contract = NULL WHERE id = 'toxsam';

-- 2. Merge the VIPE rows into vipe-heroes-genesis.
UPDATE collections
SET contract          = '0x3999877754904d8542ad1845d368fa01a5e6e9a5',
    total_supply      = COALESCE(total_supply, 3000),
    max_supply        = COALESCE(max_supply, 3000),
    max_supply_source = COALESCE(max_supply_source,
                                 'onchain:ethereum:0x39998777:totalSupply@2026-08-10'),
    opensea_slug      = COALESCE(NULLIF(opensea_slug, ''),
                                 (SELECT opensea_slug FROM collections WHERE id = 'vipe-heroes')),
    banner_image_url  = COALESCE(NULLIF(banner_image_url, ''),
                                 (SELECT banner_image_url FROM collections WHERE id = 'vipe-heroes')),
    image_url         = COALESCE(NULLIF(image_url, ''),
                                 (SELECT image_url FROM collections WHERE id = 'vipe-heroes')),
    description       = COALESCE(NULLIF(description, ''),
                                 (SELECT description FROM collections WHERE id = 'vipe-heroes')),
    vipe_category     = COALESCE(vipe_category,
                                 (SELECT vipe_category FROM collections WHERE id = 'vipe-heroes')),
    vipe_assets_3d    = COALESCE(vipe_assets_3d,
                                 (SELECT vipe_assets_3d FROM collections WHERE id = 'vipe-heroes')),
    curated_description = COALESCE(curated_description,
                                 (SELECT curated_description FROM collections WHERE id = 'vipe-heroes'))
WHERE id = 'vipe-heroes-genesis';

UPDATE contracts             SET collection_id = 'vipe-heroes-genesis' WHERE collection_id = 'vipe-heroes';
UPDATE avatars               SET collection_id = 'vipe-heroes-genesis' WHERE collection_id = 'vipe-heroes';
DELETE FROM collection_identifiers WHERE collection_id = 'vipe-heroes'
   AND value IN (SELECT value FROM collection_identifiers WHERE collection_id = 'vipe-heroes-genesis');
UPDATE collection_identifiers SET collection_id = 'vipe-heroes-genesis' WHERE collection_id = 'vipe-heroes';
DELETE FROM license_dimensions WHERE collection_id = 'vipe-heroes';
DELETE FROM collections        WHERE id = 'vipe-heroes';

-- 3. Give the Ethereum NeonGlitch86 row its contract (source: Open Source Avatars).
UPDATE collections
SET contract = '0x776bd31ae5549eac9ed215b5db278229454d5bed'
WHERE id = 'NeonGlitch86-collection' AND (contract IS NULL OR contract = '');
