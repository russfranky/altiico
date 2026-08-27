# ADR 0007 — Individual avatar route and identity contract
**Status:** Accepted

Use `/explore/avatar-sets/[setSlug]/avatars/[avatarSlug]`. Keep product, source, API, contract, and token identities separate.

## Unix philosophy check
- **Single responsibility:** The route presents one product avatar identity.
- **Composability:** Product identity and source evidence meet through the catalog port.
- **Data boundary:** Separate typed identity fields cross contracts.
- **Failure behavior:** Source identity cannot silently replace public route identity.
- **Simplicity:** Token identity is not used as a shortcut for product identity.
