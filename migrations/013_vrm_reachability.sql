-- 013_vrm_reachability.sql
--
-- Track whether a collection's VRM file is actually reachable — the biggest
-- onboarding blocker. Populated by scripts/check_vrm_reachable.py, surfaced in
-- the catalog UI as a live/dead badge + filter.
--
--   vrm_reachable      1 = a VRM byte-stream was fetched, 0 = unreachable, NULL = unchecked
--   vrm_check_status   ok_vrm | reachable_not_vrm | http_404 | http_5xx | timeout |
--                      dns_or_conn | no_url | error
--   vrm_check_http     last HTTP status code seen (nullable)
--   vrm_check_bytes    GLB total length when ok_vrm (nullable)
--   vrm_check_url      the concrete URL that was tested (may be a rewritten IPFS gateway)
--   vrm_checked_at     ISO 8601 timestamp of the check
--
-- Apply:  sqlite3 data/vrm_index.db < migrations/013_vrm_reachability.sql

ALTER TABLE collections ADD COLUMN vrm_reachable    INTEGER;
ALTER TABLE collections ADD COLUMN vrm_check_status TEXT;
ALTER TABLE collections ADD COLUMN vrm_check_http   INTEGER;
ALTER TABLE collections ADD COLUMN vrm_check_bytes  INTEGER;
ALTER TABLE collections ADD COLUMN vrm_check_url    TEXT;
ALTER TABLE collections ADD COLUMN vrm_checked_at   TEXT;
