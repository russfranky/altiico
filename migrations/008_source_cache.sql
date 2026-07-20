-- Migration 008: source_cache
--
-- A TTL-based cache for API responses so enrichment scripts can avoid
-- re-fetching data that hasn't expired yet. Stores the raw response body
-- alongside HTTP cache validators (ETag, Last-Modified) for conditional
-- revalidation, and the HTTP status code so callers can react to 404/429
-- responses without re-parsing the body.

CREATE TABLE IF NOT EXISTS source_cache (
    key            TEXT     NOT NULL PRIMARY KEY,  -- e.g. 'opensea:collection:pixelbeasts:meta', 'opensea:stats:pixelbeasts', 'opensea:batch:meta'
    endpoint       TEXT     NOT NULL,              -- e.g. 'collection_meta', 'collection_stats', 'batch_collections', 'nft'
    fetched_at     TEXT     NOT NULL,              -- ISO 8601 timestamp
    expires_at     TEXT     NOT NULL,              -- ISO 8601 timestamp
    etag           TEXT,                           -- HTTP ETag for conditional revalidation
    last_modified  TEXT,                           -- HTTP Last-Modified for conditional revalidation
    status         INTEGER,                        -- HTTP status code, e.g. 200, 404, 429
    response_json  TEXT                            -- cached API response body as JSON string
);

CREATE INDEX IF NOT EXISTS idx_sc_expires
    ON source_cache(expires_at);

CREATE INDEX IF NOT EXISTS idx_sc_endpoint
    ON source_cache(endpoint);
