-- Full collection-research dimensions. These are deliberately separate from
-- Hubzz/VRM binary readiness: a technically valid VRM collection can still be
-- catalog-incomplete when identity, social, lifecycle, legal or access facts
-- are unresolved.
ALTER TABLE collections ADD COLUMN short_description TEXT;
ALTER TABLE collections ADD COLUMN project_status TEXT;
ALTER TABLE collections ADD COLUMN storage_types TEXT;
ALTER TABLE collections ADD COLUMN vrm_inventory_state TEXT;
ALTER TABLE collections ADD COLUMN vrm_inventory_count INTEGER;
ALTER TABLE collections ADD COLUMN vrm_inventory_complete INTEGER;
ALTER TABLE collections ADD COLUMN file_access_mode TEXT;
ALTER TABLE collections ADD COLUMN file_access_requires_ownership INTEGER;
ALTER TABLE collections ADD COLUMN ip_rights_summary TEXT;
ALTER TABLE collections ADD COLUMN catalog_research_evidence TEXT;
ALTER TABLE collections ADD COLUMN catalog_research_updated_at TEXT;

CREATE TABLE IF NOT EXISTS catalog_research_evidence (
    collection_id TEXT NOT NULL,
    field TEXT NOT NULL,
    state TEXT,
    value_json TEXT,
    evidence_json TEXT NOT NULL,
    observed_at TEXT,
    PRIMARY KEY (collection_id, field),
    FOREIGN KEY (collection_id) REFERENCES collections(id)
);

CREATE INDEX IF NOT EXISTS idx_catalog_research_state
    ON catalog_research_evidence(field, state);
