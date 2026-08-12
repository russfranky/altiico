from pathlib import Path

p = Path('scripts/opensea_client.py')
s = p.read_text()
marker = '    async def batch_collections(self, slugs: list[str]) -> dict[str, Any]:\n'
methods = '''    async def get_chains(self) -> dict[str, Any]:
        return await self._request("GET", "/chains")

    async def get_collection_traits(self, slug: str) -> dict[str, Any]:
        return await self._request("GET", f"/traits/{slug}")

    async def get_collection_events(
        self, slug: str, *, limit: int = 50, event_type: Optional[str] = None,
        after: Optional[int] = None, before: Optional[int] = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": max(1, min(int(limit), 200))}
        if event_type:
            params["event_type"] = event_type
        if after is not None:
            params["after"] = int(after)
        if before is not None:
            params["before"] = int(before)
        return await self._request("GET", f"/events/collection/{slug}", params=params)

    async def get_nft_collection(self, chain: str, contract: str, token_id: str) -> dict[str, Any]:
        os_chain = CHAIN_MAP.get(chain, chain)
        return await self._request("GET", f"/chain/{os_chain}/contract/{contract}/nfts/{token_id}/collection")

    async def get_nft_metadata(self, chain: str, contract: str, token_id: str) -> dict[str, Any]:
        os_chain = CHAIN_MAP.get(chain, chain)
        return await self._request("GET", f"/metadata/{os_chain}/{contract}/{token_id}")

    async def validate_nft_metadata(
        self, chain: str, contract: str, token_id: str, *, ignore_cached_item_urls: bool = False,
    ) -> dict[str, Any]:
        os_chain = CHAIN_MAP.get(chain, chain)
        params = {"ignoreCachedItemUrls": "true"} if ignore_cached_item_urls else None
        return await self._request(
            "POST", f"/chain/{os_chain}/contract/{contract}/nfts/{token_id}/validate-metadata", params=params
        )

    async def get_best_listings(self, slug: str, *, limit: int = 20) -> dict[str, Any]:
        return await self._request("GET", f"/listings/collection/{slug}/best", params={"limit": max(1, min(int(limit), 200))})

    async def get_collection_offers(self, slug: str, *, limit: int = 20) -> dict[str, Any]:
        return await self._request("GET", f"/offers/collection/{slug}", params={"limit": max(1, min(int(limit), 200))})

'''
if 'async def get_chains(' not in s:
    assert marker in s
    s = s.replace(marker, methods + marker)
p.write_text(s)

p = Path('scripts/export_hubzz_staging.py')
s = p.read_text()
old = '''    if not (public_url(row["banner_image_url"]) if "banner_image_url" in row.keys() else None):
        warnings.append("missing_banner")
    if not (public_url(row["image_url"]) if "image_url" in row.keys() else None):
        warnings.append("missing_pfp")
'''
new = '''    dedicated_banner = public_url(row["banner_image_url"]) if "banner_image_url" in row.keys() else None
    pfp_url = (public_url(row["image_url"]) if "image_url" in row.keys() else None) or (
        public_url(row["sample_nft_image"]) if "sample_nft_image" in row.keys() else None
    )
    banner_url = dedicated_banner or pfp_url
    banner_source = "collection_banner" if dedicated_banner else ("pfp_fallback" if pfp_url else "missing")
    banner_fallback = dedicated_banner is None and pfp_url is not None
    if banner_fallback:
        warnings.append("banner_uses_pfp_fallback")
    if not banner_url:
        warnings.append("missing_banner")
    if not pfp_url:
        warnings.append("missing_pfp")
'''
assert old in s
s = s.replace(old, new)
old2 = '''        "bannerUrl": public_url(row["banner_image_url"]) if "banner_image_url" in row.keys() else None,
        "pfpUrl": (public_url(row["image_url"]) if "image_url" in row.keys() else None)
        or (public_url(row["sample_nft_image"]) if "sample_nft_image" in row.keys() else None),
'''
new2 = '''        "bannerUrl": banner_url,
        "pfpUrl": pfp_url,
'''
assert old2 in s
s = s.replace(old2, new2)
marker2 = '''        "warnings": warnings,
    }
'''
replace2 = '''        "bannerEvidence": {
            "url": banner_url,
            "source": banner_source,
            "fallback": banner_fallback,
            "observedAt": generated_at,
        },
        "warnings": warnings,
    }
'''
assert marker2 in s
s = s.replace(marker2, replace2, 1)
validate_marker = '''        if record.get("status") != "staged" or record.get("listed") is not False:
            errors.append(f"{prefix}: must be staged and unlisted")
'''
validate_new = validate_marker + '''        if not public_url(record.get("bannerUrl")):
            errors.append(f"{prefix}: missing public bannerUrl")
        banner_evidence = item.get("bannerEvidence") or {}
        if banner_evidence.get("url") != record.get("bannerUrl"):
            errors.append(f"{prefix}: banner evidence mismatch")
        if banner_evidence.get("source") not in {"collection_banner", "pfp_fallback"}:
            errors.append(f"{prefix}: invalid banner evidence source")
        if record.get("bannerUrl") == record.get("pfpUrl") and banner_evidence.get("fallback") is not True:
            errors.append(f"{prefix}: banner/PFP reuse must be explicit fallback")
'''
assert validate_marker in s
s = s.replace(validate_marker, validate_new, 1)
p.write_text(s)

p = Path('tests/test_opensea_client.py')
s = p.read_text()
addition = '''\n\ndef test_catalog_read_surfaces_use_current_routes():
    client = OpenSeaClient(api_key="test")
    calls = []
    async def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return {"ok": True}
    client._request = fake_request
    async def exercise():
        await client.get_chains()
        await client.get_collection_traits("avatars")
        await client.get_collection_events("avatars", limit=200)
        await client.get_nft_collection("ethereum", "0xabc", "1")
        await client.get_nft_metadata("ethereum", "0xabc", "1")
        await client.validate_nft_metadata("ethereum", "0xabc", "1", ignore_cached_item_urls=True)
        await client.get_best_listings("avatars", limit=10)
        await client.get_collection_offers("avatars", limit=10)
    asyncio.run(exercise())
    routes = [(method, url) for method, url, _ in calls]
    assert ("GET", "/chains") in routes
    assert ("GET", "/traits/avatars") in routes
    assert ("GET", "/events/collection/avatars") in routes
    assert ("GET", "/chain/ethereum/contract/0xabc/nfts/1/collection") in routes
    assert ("GET", "/metadata/ethereum/0xabc/1") in routes
    assert ("POST", "/chain/ethereum/contract/0xabc/nfts/1/validate-metadata") in routes
    assert ("GET", "/listings/collection/avatars/best") in routes
    assert ("GET", "/offers/collection/avatars") in routes
'''
if 'test_catalog_read_surfaces_use_current_routes' not in s:
    s += addition
p.write_text(s)
