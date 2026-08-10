-- 020_avatar_reachability.sql
--
-- Per-avatar reachability. Collection-level checks only ever validated ONE
-- sample VRM per collection; these columns record whether each of the 4,274
-- individual avatar files actually resolves.
--
--   reachable    1 = a GLB byte-stream was served, 0 = not, NULL = unchecked
--   check_status ok_glb | not_glb | http_404 | http_403 | http_5xx | timeout |
--                dns_or_conn | error
--   check_http   last HTTP status seen
--   checked_at   ISO 8601 timestamp
--
-- Apply:  sqlite3 data/vrm_index.db < migrations/020_avatar_reachability.sql

ALTER TABLE avatars ADD COLUMN reachable    INTEGER;
ALTER TABLE avatars ADD COLUMN check_status TEXT;
ALTER TABLE avatars ADD COLUMN check_http   INTEGER;
ALTER TABLE avatars ADD COLUMN checked_at   TEXT;
