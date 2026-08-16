# Release process

Altiico Catalog is pre-1.0. Releases identify coherent code and artifact contracts, not completion of the full research catalog.

## Versioning

Use Semantic Versioning where practical:

- patch: fixes that preserve documented schemas and acceptance meaning;
- minor: new compatible sources, fields, commands, or public features;
- major: incompatible schema or acceptance contract changes.

Before 1.0, a minor release may contain a breaking change. Call it out prominently in the changelog and release notes.

## Release checklist

1. Confirm the target commit is on `main` and all required checks pass.
2. Run:

   ```bash
   make verify
   make test
   python scripts/verify_catalog_consistency.py
   python scripts/project_status.py
   ```

3. Confirm generated artifacts share one snapshot identity.
4. Review `data/catalog_acceptance.json` and the Hubzz deferred queue for unexpected claim changes.
5. Update [CHANGELOG.md](../CHANGELOG.md), moving relevant entries from `Unreleased` into the release version and date.
6. Confirm README, schema docs, and migration notes match the code.
7. Create an annotated tag such as `v0.1.0` from the verified commit.
8. Create a GitHub release from the tag with:
   - changes and user impact;
   - schema or gate changes;
   - current catalog acceptance and staging status;
   - migration instructions;
   - known limitations;
   - the snapshot identifier.
9. Verify the production catalog deployment points at the intended snapshot.

## Rollback

A deployment rollback may restore the previous static build. Do not rewrite a published tag. If released code or data is incorrect, publish a corrective patch release and preserve the original snapshot for provenance.

## Data corrections

A catalog correction can be release-worthy even when application code is unchanged. Release notes must distinguish:

- stronger evidence that promotes a collection;
- corrected identity or rights information that demotes or defers a collection;
- source availability changes;
- schema or validation behavior changes.

Correctness outranks monotonic growth. A release may intentionally reduce passing or stageable counts.
