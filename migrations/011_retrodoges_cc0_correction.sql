-- 011_retrodoges_cc0_correction.sql
--
-- Data correction: RetroDoges (retrodogesnft) is released under CC0
-- ("no rights reserved" — public domain: full commercial use, modification and
-- derivatives, no attribution, non-holders may use the art). The prior record
-- had it as red / Redistribution_Prohibited / OnlyAuthor, which was wrong; that
-- value likely came from embedded VRM meta and is superseded by the confirmed
-- collection license. Owner-confirmed 2026-08-09.
--
-- Apply:  sqlite3 data/vrm_index.db < migrations/011_retrodoges_cc0_correction.sql

UPDATE collections
SET license_category = 'green',
    vrm_license      = 'CC0',
    commercial_use   = 'Allow',
    allowed_user     = 'Everyone',
    redistribution   = 'Allow'
WHERE id = 'retrodogesnft';

-- Keep the normalized license_dimensions row in sync (CC0 mapping mirrors
-- config/license-mapping.yaml: creative_commons.CC0).
UPDATE license_dimensions
SET use_scope             = 'everyone',
    commercial_scope      = 'personal_profit',
    credit                = 'unnecessary',
    redistribute_original = 1,
    modify                = 1,
    redistribute_modified = 1,
    corporate_use         = 0,
    terminates_on_transfer = 0,
    color                 = 'green',
    reason_codes          = '[]',
    confidence            = 'manual',
    conflict_flag         = 0,
    assessed_at           = '2026-08-09T00:00:00Z'
WHERE collection_id = 'retrodogesnft';
