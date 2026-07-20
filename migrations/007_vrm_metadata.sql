-- Migration 007: vrm_metadata
--
-- VRM files are binary glTF (GLB) with embedded license/permission metadata in
-- the first JSON chunk. Many avatars may share the same VRM file URL, so
-- vrm_metadata holds one row per unique source URL (deduplicated) and
-- avatar_vrm links each avatar to its VRM file.

CREATE TABLE IF NOT EXISTS vrm_metadata (
    source_url        TEXT     NOT NULL PRIMARY KEY,  -- canonical VRM URL, deduplicated
    source_etag       TEXT,                            -- HTTP ETag for cache validation
    source_last_modified TEXT,                         -- HTTP Last-Modified
    extracted_at      TEXT     NOT NULL,               -- ISO 8601 timestamp of extraction
    extractor_version TEXT     NOT NULL,               -- e.g. "1.0.0"
    vrm_spec          TEXT,                            -- "0.x" or "1.0"
    vrm_meta_json     TEXT,                            -- raw embedded VRM metadata, verbatim
    parse_error       TEXT,                            -- error message if extraction failed
    content_length    INTEGER,                         -- total GLB file size in bytes
    content_range     TEXT                             -- Content-Range header value if partial download
);

CREATE TABLE IF NOT EXISTS avatar_vrm (
    avatar_id      TEXT NOT NULL PRIMARY KEY,          -- references avatars.id
    vrm_source_url TEXT NOT NULL,                      -- references vrm_metadata.source_url
    FOREIGN KEY (avatar_id) REFERENCES avatars(id),
    FOREIGN KEY (vrm_source_url) REFERENCES vrm_metadata(source_url)
);

CREATE INDEX IF NOT EXISTS idx_av_vrm_url
    ON avatar_vrm(vrm_source_url);
