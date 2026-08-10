-- 014_hubzz_readiness.sql
--
-- Hubzz-ingress readiness. A collection is READY to onboard into hubzz when all
-- CRITICAL criteria pass; readiness_score (0-8) also counts completeness
-- criteria so partial sets can be prioritised. Populated by
-- scripts/score_readiness.py; surfaced in the catalog UI (filter + badge).
--
--   ready               1 = all critical criteria met, else 0
--   readiness_score     count of criteria met, 0-8
--   readiness_criteria  JSON object of {criterion: bool}
--   readiness_at        ISO 8601 timestamp
--
-- Critical (gate ingress):  vrm_ok, license_ok, identity_ok
-- Completeness (full set):  banner_ok, pfp_ok, desc_ok, social_ok, count_ok
--
-- Apply:  sqlite3 data/vrm_index.db < migrations/014_hubzz_readiness.sql

ALTER TABLE collections ADD COLUMN ready              INTEGER;
ALTER TABLE collections ADD COLUMN readiness_score    INTEGER;
ALTER TABLE collections ADD COLUMN readiness_criteria TEXT;
ALTER TABLE collections ADD COLUMN readiness_at       TEXT;
