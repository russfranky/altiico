-- 015_license_and_supply_fixes.sql
--
-- Two evidence-backed data corrections found while closing readiness blockers.
--
-- 1. ToxSam: license_category was the literal 'CC0', which is not part of the
--    category vocabulary (green|yellow|red|unknown), so every downstream check
--    treated it as unusable. CC0 is the most permissive license -> 'green'.
--    The raw license string is preserved in vrm_license.
--
-- 2. VIPE Heroes: total_supply was 2779; the contract
--    0x3999877754904d8542ad1845d368fa01a5e6e9a5 reports totalSupply() = 3000
--    on Ethereum mainnet (name "VIPE Heroes", symbol VPH), verified 2026-08-10.
--
-- NOT done here (needs a human ruling, see data/discovery_leads.yaml):
--    `vipe-heroes` and `vipe-heroes-genesis` are the SAME collection split
--    across two rows — one carries the contract, the other carries the 3000
--    avatars. Merging changes collection identity, so it is not automated.
--
-- Apply:  sqlite3 data/vrm_index.db < migrations/015_license_and_supply_fixes.sql

UPDATE collections
SET license_category = 'green',
    vrm_license = COALESCE(NULLIF(vrm_license, ''), 'CC0')
WHERE id = 'toxsam' AND license_category = 'CC0';

UPDATE collections
SET total_supply = 3000,
    max_supply = 3000,
    max_supply_source = 'onchain:ethereum:0x39998777:totalSupply@2026-08-10'
WHERE id = 'vipe-heroes';
