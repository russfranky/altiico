-- 016_hubzz_presence.sql
--
-- Track whether a collection is ALREADY in Hubzz. Without this the readiness
-- scorecard surfaced sets that are long since onboarded (RetroDoges, VIPE
-- Heroes, Grifters Squaddies), which made the "ready to onboard" list actively
-- misleading — the whole point is to find what is NOT yet in.
--
--   hubzz_status     onboarded | partial | absent
--                      onboarded = present and every avatar optimized/served
--                      partial   = present but not fully optimized (or a junk row)
--                      absent    = not in Hubzz at all  <- the actionable set
--   hubzz_slug       the matching set slug in the Hubzz avatar registry
--   hubzz_optimized  count of optimized avatars in Hubzz for that set
--   hubzz_rows       count of avatar rows in Hubzz for that set
--   hubzz_synced_at  ISO 8601 timestamp of the last sync
--
-- Populated by scripts/sync_hubzz_status.py from the live avatars.db.
--
-- Apply:  sqlite3 data/vrm_index.db < migrations/016_hubzz_presence.sql

ALTER TABLE collections ADD COLUMN hubzz_status    TEXT;
ALTER TABLE collections ADD COLUMN hubzz_slug      TEXT;
ALTER TABLE collections ADD COLUMN hubzz_optimized INTEGER;
ALTER TABLE collections ADD COLUMN hubzz_rows      INTEGER;
ALTER TABLE collections ADD COLUMN hubzz_synced_at TEXT;
