# Catalog artifact integrity

Every generated catalog projection is now bound to a deterministic snapshot of
SQLite evidence. The snapshot is derived from durable schema and rows, excluding
only transient HTTP caches and the snapshot ledger itself.

The following files must carry the same identifier:

- `static/data/build-info.json`
- the current content-hashed `collections.*.json`
- `static/data/avatar-manifest-v1.json`
- `static/data/avatars-registry.json`
- `static/data/hubzz-prealpha-staging.json`
- every `static/data/hubzz-prealpha-source/*.json` sidecar

Run the hard gate with:

```bash
python scripts/export_hubzz_manifest.py --validate
python scripts/export_avatars_registry.py
python scripts/export_hubzz_staging.py --validate
python scripts/build_catalog.py
python scripts/verify_catalog_consistency.py
```

`verify_catalog_consistency.py` compares the artifacts to the current database,
checks canonical contracts across projections, verifies sidecar snapshots, and
scans deployable static files for exact configured secrets and common token
patterns.

VRM validation now retains two distinct digests:

- `content_sha256`: SHA-256 of the complete bounded VRM binary
- `json_chunk_sha256`: SHA-256 of the GLB JSON chunk used for structural parsing

The IPFS CID or Arweave transaction remains the canonical decentralized
identity. The complete-file SHA-256 proves the exact bytes later mirrored or
optimized by Hubzz.
