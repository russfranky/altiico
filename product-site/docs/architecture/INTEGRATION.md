# Public product-site integration

## Repository arrangement

The existing repository root remains the evidence pipeline during the public-site build.

The new Next.js experience lives under `product-site/` until cutover.

## Durable boundary

```text
root evidence pipeline
  -> versioned staging evidence
  -> typed adapter
  -> canonical Altiico product model
  -> public product site
```

The evidence pipeline can later move to `services/catalog-evidence/` without changing the web contract.

## Precedence

Product-owned values win for product IDs, public slugs, display state, and future API row identity.

Evidence can fill technical fields and provenance. Evidence cannot silently publish or rename a product record.

## Public safety

The current public catalog stays unchanged on `main` until the new product site passes visual, contract, and deployment review.
