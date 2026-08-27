# ADR 0012 — Source-neutral immutable product records
**Status:** Accepted

Use opaque provenance data instead of concrete source unions. Keep product records readonly. Remove internal migration copy from public screens.

## Unix philosophy check
- **Single responsibility:** Adapters name sources; domain describes product data; presentation formats supplied provenance.
- **Composability:** The catalog port and readonly provenance objects connect the layers.
- **Data boundary:** Provenance is plain readonly data with source ID, mode, and optional snapshot ID.
- **Failure behavior:** Missing records return null; unexpected source failure reaches the error boundary.
- **Simplicity:** The decision removes source captivity and mutable record surfaces.
