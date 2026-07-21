-- Migration 010: license_dimensions
--
-- The legacy license model used a single `license_category` column
-- (green/yellow/red/unknown) plus free-text columns on the collections table
-- (vrm_license, commercial_use, allowed_user, redistribution). That collapses
-- several independent permissions into one coarse bucket and loses the raw
-- terms that produced it.
--
-- This migration introduces a `license_dimensions` table that decomposes
-- license permissions into independent normalized dimensions while preserving
-- the raw source terms verbatim. One row per collection. The legacy columns on
-- `collections` are left in place for backward compatibility; the normalized
-- table is the authoritative source going forward.
--
-- Dimension vocabulary (see config/license-mapping.yaml for the full mapping):
--   use_scope          everyone | holder | explicitly_licensed | author | unknown
--   commercial_scope   none | personal_non_profit | personal_profit | corporation | unknown
--   credit             required | unnecessary | unknown
--   boolean dims       0/1/NULL (NULL = unspecified, not "false")
--     redistribute_original, modify, redistribute_modified, corporate_use,
--     terminates_on_transfer, hate_speech_termination
--   color              green | yellow | red | gray (gray replaces legacy "unknown")
--   confidence         embedded | collection | manual | unknown
--   reason_codes       JSON array of strings, e.g. ["HOLDER_ONLY","REDISTRIBUTION_PROHIBITED"]

CREATE TABLE IF NOT EXISTS license_dimensions (
    collection_id              TEXT     PRIMARY KEY,
    raw_collection_terms       TEXT,    -- JSON of raw collection-level terms, preserved verbatim
    raw_embedded_vrm_meta_json TEXT,    -- raw VRM meta JSON, preserved verbatim
    raw_external_urls          TEXT,    -- JSON array of external license URLs
    use_scope                  TEXT,    -- everyone, holder, explicitly_licensed, author, unknown
    commercial_scope           TEXT,    -- none, personal_non_profit, personal_profit, corporation, unknown
    credit                     TEXT,    -- required, unnecessary, unknown
    redistribute_original      INTEGER, -- 0/1/NULL
    modify                     INTEGER, -- 0/1/NULL
    redistribute_modified      INTEGER, -- 0/1/NULL
    corporate_use              INTEGER, -- 0/1/NULL
    terminates_on_transfer     INTEGER, -- 0/1/NULL
    hate_speech_termination    INTEGER, -- 0/1/NULL
    color                      TEXT,    -- green, yellow, red, gray
    reason_codes               TEXT,    -- JSON array of strings
    confidence                 TEXT,    -- embedded, collection, manual, unknown
    conflict_flag              INTEGER  DEFAULT 0,
    assessed_at                TEXT,    -- ISO 8601 timestamp
    FOREIGN KEY (collection_id) REFERENCES collections(id)
);

CREATE INDEX IF NOT EXISTS idx_ld_color
    ON license_dimensions(color);

CREATE INDEX IF NOT EXISTS idx_ld_confidence
    ON license_dimensions(confidence);

CREATE INDEX IF NOT EXISTS idx_ld_conflict
    ON license_dimensions(conflict_flag);

-- Backfill: one row per existing collection. Color is derived from the legacy
-- license_category (unknown → gray); confidence is 'legacy' to distinguish
-- backfilled rows from freshly assessed ones. Raw terms and normalized
-- dimensions are populated later by scripts/normalize_licenses.py.
INSERT OR IGNORE INTO license_dimensions
    (collection_id, raw_collection_terms, color, confidence, assessed_at)
SELECT
    id,
    json_object(
        'vrm_license',       vrm_license,
        'commercial_use',    commercial_use,
        'allowed_user',      allowed_user,
        'redistribution',    redistribution,
        'license_category',  license_category
    ),
    CASE license_category
        WHEN 'green'  THEN 'green'
        WHEN 'yellow' THEN 'yellow'
        WHEN 'red'    THEN 'red'
        ELSE 'gray'
    END,
    'legacy',
    strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
FROM collections;
