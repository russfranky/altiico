-- 023_artifact_snapshots.sql
--
-- Add deterministic export snapshots and preserve both complete-file and
-- JSON-chunk digests for validated VRM binaries.
--
-- Apply once:
--   sqlite3 data/vrm_index.db < migrations/023_artifact_snapshots.sql

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS artifact_snapshots (
    snapshot_id          TEXT PRIMARY KEY,
    db_sha256            TEXT NOT NULL,
    materializer_version TEXT NOT NULL,
    source_cutoff_json   TEXT NOT NULL DEFAULT '{}',
    created_at           TEXT NOT NULL
);

ALTER TABLE vrm_metadata ADD COLUMN content_sha256 TEXT;
ALTER TABLE vrm_metadata ADD COLUMN json_chunk_sha256 TEXT;
ALTER TABLE vrm_metadata ADD COLUMN observed_content_length INTEGER;
ALTER TABLE vrm_metadata ADD COLUMN transport_url TEXT;

CREATE INDEX IF NOT EXISTS idx_vrm_metadata_content_sha256
    ON vrm_metadata(content_sha256);

-- Reconcile the validated Chuddies deployment. The token-127 crawl
-- established 0x6b67... as the canonical VRM-bearing contract.
UPDATE collections
SET contract = '0x6b67b34dfded7cf3b32cab94045aa82da2cc4bd9'
WHERE id = 'chuddie';

UPDATE contracts
SET is_primary = CASE
    WHEN lower(address) = '0x6b67b34dfded7cf3b32cab94045aa82da2cc4bd9' THEN 1
    ELSE 0
END
WHERE collection_id = 'chuddie';

UPDATE collection_identifiers
SET value = '0x6b67b34dfded7cf3b32cab94045aa82da2cc4bd9',
    contract = '0x6b67b34dfded7cf3b32cab94045aa82da2cc4bd9'
WHERE collection_id = 'chuddie' AND namespace = 'contract_token';

UPDATE collection_identifiers
SET contract = '0x6b67b34dfded7cf3b32cab94045aa82da2cc4bd9'
WHERE collection_id = 'chuddie' AND namespace = 'opensea_slug';
