-- 022_recursive_crawler.sql
--
-- Durable state for the seed-driven recursive catalog crawler. The crawler
-- stores intrinsic resources once per run, then attaches any number of
-- collection/avatar bindings to the same task. This keeps network work
-- deduplicated without losing provenance.
--
-- Apply manually, consistent with the rest of this repository:
--   sqlite3 data/vrm_index.db < migrations/022_recursive_crawler.sql

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS crawl_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    status          TEXT NOT NULL CHECK (
        status IN ('running', 'completed', 'budget_exhausted', 'failed')
    ),
    config_json     TEXT NOT NULL,
    request_budget  INTEGER NOT NULL,
    requests_used   INTEGER NOT NULL DEFAULT 0,
    root_seed_count INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT
);

CREATE TABLE IF NOT EXISTS crawl_tasks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL,
    kind            TEXT NOT NULL CHECK (
        kind IN ('metadata', 'asset', 'evm_token')
    ),
    canonical_key   TEXT NOT NULL,
    payload_json    TEXT NOT NULL,
    depth           INTEGER NOT NULL,
    priority        INTEGER NOT NULL DEFAULT 100,
    state           TEXT NOT NULL CHECK (
        state IN ('queued', 'leased', 'retry', 'done', 'rejected', 'permanent_error')
    ),
    attempts        INTEGER NOT NULL DEFAULT 0,
    available_at    TEXT,
    lease_until     TEXT,
    last_error      TEXT,
    created_at      TEXT NOT NULL,
    completed_at    TEXT,
    FOREIGN KEY (run_id) REFERENCES crawl_runs(id) ON DELETE CASCADE,
    UNIQUE (run_id, kind, canonical_key)
);

CREATE INDEX IF NOT EXISTS idx_crawl_tasks_claim
    ON crawl_tasks(run_id, state, available_at, priority, depth, id);

CREATE TABLE IF NOT EXISTS crawl_bindings (
    task_id         INTEGER NOT NULL,
    collection_id   TEXT NOT NULL DEFAULT '',
    avatar_id       TEXT NOT NULL DEFAULT '',
    seed_source     TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (task_id, collection_id, avatar_id, seed_source),
    FOREIGN KEY (task_id) REFERENCES crawl_tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_crawl_bindings_collection
    ON crawl_bindings(collection_id);

CREATE INDEX IF NOT EXISTS idx_crawl_bindings_avatar
    ON crawl_bindings(avatar_id);

CREATE TABLE IF NOT EXISTS crawl_edges (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL,
    parent_task_id  INTEGER NOT NULL,
    child_task_id   INTEGER NOT NULL,
    relation        TEXT NOT NULL,
    json_path       TEXT NOT NULL DEFAULT '',
    reason          TEXT NOT NULL DEFAULT '',
    confidence      REAL NOT NULL DEFAULT 0.5,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES crawl_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_task_id) REFERENCES crawl_tasks(id) ON DELETE CASCADE,
    FOREIGN KEY (child_task_id) REFERENCES crawl_tasks(id) ON DELETE CASCADE,
    UNIQUE (run_id, parent_task_id, child_task_id, relation, json_path)
);

CREATE INDEX IF NOT EXISTS idx_crawl_edges_parent
    ON crawl_edges(parent_task_id);

CREATE INDEX IF NOT EXISTS idx_crawl_edges_child
    ON crawl_edges(child_task_id);

CREATE TABLE IF NOT EXISTS crawl_observations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL,
    task_id         INTEGER NOT NULL,
    predicate       TEXT NOT NULL,
    value_json      TEXT NOT NULL,
    source_url      TEXT NOT NULL DEFAULT '',
    json_path       TEXT NOT NULL DEFAULT '',
    confidence      REAL NOT NULL DEFAULT 0.5,
    content_sha256  TEXT NOT NULL DEFAULT '',
    observed_at     TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES crawl_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES crawl_tasks(id) ON DELETE CASCADE,
    UNIQUE (task_id, predicate, value_json, json_path, source_url)
);

CREATE INDEX IF NOT EXISTS idx_crawl_observations_predicate
    ON crawl_observations(run_id, predicate);

CREATE TABLE IF NOT EXISTS crawl_resources (
    canonical_url   TEXT PRIMARY KEY,
    final_url       TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL,
    http_status     INTEGER,
    content_type    TEXT NOT NULL DEFAULT '',
    body_sha256     TEXT NOT NULL DEFAULT '',
    body_text       TEXT,
    etag            TEXT NOT NULL DEFAULT '',
    last_modified   TEXT NOT NULL DEFAULT '',
    fetched_at      TEXT NOT NULL,
    expires_at      TEXT NOT NULL,
    error_class     TEXT NOT NULL DEFAULT '',
    error_message   TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_crawl_resources_expiry
    ON crawl_resources(expires_at);

CREATE TABLE IF NOT EXISTS crawl_materializations (
    run_id          INTEGER NOT NULL,
    collection_id   TEXT NOT NULL,
    avatar_id       TEXT NOT NULL DEFAULT '',
    field_name      TEXT NOT NULL,
    old_value       TEXT,
    new_value       TEXT,
    materialized_at TEXT NOT NULL,
    PRIMARY KEY (run_id, collection_id, avatar_id, field_name),
    FOREIGN KEY (run_id) REFERENCES crawl_runs(id) ON DELETE CASCADE
);
