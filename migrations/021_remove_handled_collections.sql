-- 021_remove_handled_collections.sql
--
-- Owner-directed removal (2026-08-10). These eight collections are already
-- handled in Hubzz and are not research targets, so they are noise in a
-- discovery/vetting catalog:
--
--   100Avatars R1 / R2 / R3, Grifters Squaddies, RetroDoges,
--   ToxSam, ToxSam (Base side), VIPE Heroes Genesis
--
-- Deletes each collection and everything it owns (avatars, contracts,
-- identifiers, license dimensions). A DB backup was taken to /tmp first.
--
-- Apply:  sqlite3 data/vrm_index.db < migrations/021_remove_handled_collections.sql

CREATE TEMP TABLE _doomed(id TEXT PRIMARY KEY);
INSERT INTO _doomed(id) VALUES
  ('100avatars-r1'), ('100avatars-r2'), ('100avatars-r3'),
  ('grifterssquaddies'), ('retrodogesnft'),
  ('toxsam'), ('toxsam-base-side'), ('vipe-heroes-genesis');

DELETE FROM avatars                WHERE collection_id IN (SELECT id FROM _doomed);
DELETE FROM contracts              WHERE collection_id IN (SELECT id FROM _doomed);
DELETE FROM collection_identifiers WHERE collection_id IN (SELECT id FROM _doomed);
DELETE FROM license_dimensions     WHERE collection_id IN (SELECT id FROM _doomed);
DELETE FROM collections            WHERE id IN (SELECT id FROM _doomed);
