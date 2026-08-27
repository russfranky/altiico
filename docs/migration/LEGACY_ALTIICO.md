# Legacy Altiico migration boundary

The existing root pipeline remains an evidence producer.

It owns discovery, source consensus, binary VRM validation, acceptance gates, deterministic snapshots, and provenance.

The web app owns public product identity, routes, presentation, and interaction.

A future physical migration can move evidence code under `services/catalog-evidence/`, but the web app must continue to consume versioned serialized artifacts through `AvatarCatalogPort`.

Do not let legacy source slugs, contract IDs, token IDs, or database rows become public product identity automatically.
