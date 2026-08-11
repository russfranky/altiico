-- 024_vrm_link_reconciliation.sql
--
-- Promote two independently revalidated canonical IPFS assets:
--   * Boomboxheads token 30 replaces the timed-out token 386 sample.
--   * Phettaverse keeps the same CID/path but no longer depends on a private
--     custom Pinata gateway for its canonical source identity.
--
-- The older crawl observations remain intact as historical evidence.

PRAGMA foreign_keys = ON;

UPDATE collections
SET vrm_url_https = 'ipfs://QmURAuSRmFFAyragN3h6M6thhMhBPQmNgoNJApDSvob3D5/30.vrm',
    vrm_reachable = 1,
    vrm_check_status = 'ok_vrm',
    vrm_check_http = 200,
    vrm_check_bytes = 3139032,
    vrm_check_url = 'https://bafybeic2j2ldu6rp33e6ykbm2xkx2bpt5piddf5c5jl6dzneet2xdtgisq.ipfs.dweb.link/30.vrm',
    vrm_checked_at = '2026-08-11T20:16:07Z'
WHERE id = 'boomboxheads-v2';

UPDATE collections
SET vrm_url_https = 'ipfs://QmZYVVP2XMNK2mjcrac6zyocvAU9xuEupZ4zYuoPVuimr7/borgormachinelowpoly.vrm',
    vrm_reachable = 1,
    vrm_check_status = 'ok_vrm',
    vrm_check_http = 200,
    vrm_check_bytes = 1698236,
    vrm_check_url = 'https://ipfs.io/ipfs/QmZYVVP2XMNK2mjcrac6zyocvAU9xuEupZ4zYuoPVuimr7/borgormachinelowpoly.vrm',
    vrm_checked_at = '2026-08-11T20:16:07Z'
WHERE id = 'phettaverse-editions';

-- Remove the superseded failed sample from active binary evidence. Historical
-- crawl tasks and observations still preserve the attempted token 386 URL.
DELETE FROM vrm_metadata
WHERE source_url IN (
    'ipfs://QmURAuSRmFFAyragN3h6M6thhMhBPQmNgoNJApDSvob3D5/386.vrm',
    'https://ipfs.io/ipfs/QmURAuSRmFFAyragN3h6M6thhMhBPQmNgoNJApDSvob3D5/386.vrm',
    'https://bafybeic2j2ldu6rp33e6ykbm2xkx2bpt5piddf5c5jl6dzneet2xdtgisq.ipfs.dweb.link/386.vrm'
);

INSERT INTO vrm_metadata (
    source_url,
    extracted_at,
    extractor_version,
    vrm_spec,
    vrm_meta_json,
    parse_error,
    content_length,
    content_sha256,
    json_chunk_sha256,
    observed_content_length,
    transport_url
) VALUES (
    'ipfs://QmURAuSRmFFAyragN3h6M6thhMhBPQmNgoNJApDSvob3D5/30.vrm',
    '2026-08-11T20:16:07Z',
    'recursive-crawler-2',
    '0.x',
    '{"title":"Boomboxhead #31","version":"0.x","author":"Boomboxhead","contactInformation":"http://twitter.com/boomboxheads","reference":"https://github.com/gm3/boom-tools","allowedUserName":"Everyone","violentUssageName":"Allow","sexualUssageName":"Allow","commercialUssageName":"Allow","otherPermissionUrl":"","licenseName":"CC0","otherLicenseUrl":"","texture":8}',
    NULL,
    3139032,
    '5d18c11340e8674a08c6892ec3f6355c75aa939be2cd231d17f849a6ed234c83',
    '2f4d6a859b10a8ed05afb3b948f4fdf882b84d5ab4dc08881f4bded4c2dda5c8',
    3139032,
    'https://bafybeic2j2ldu6rp33e6ykbm2xkx2bpt5piddf5c5jl6dzneet2xdtgisq.ipfs.dweb.link/30.vrm'
)
ON CONFLICT(source_url) DO UPDATE SET
    extracted_at = excluded.extracted_at,
    extractor_version = excluded.extractor_version,
    vrm_spec = excluded.vrm_spec,
    vrm_meta_json = excluded.vrm_meta_json,
    parse_error = excluded.parse_error,
    content_length = excluded.content_length,
    content_sha256 = excluded.content_sha256,
    json_chunk_sha256 = excluded.json_chunk_sha256,
    observed_content_length = excluded.observed_content_length,
    transport_url = excluded.transport_url;

INSERT INTO vrm_metadata (
    source_url,
    extracted_at,
    extractor_version,
    vrm_spec,
    vrm_meta_json,
    parse_error,
    content_length,
    content_sha256,
    json_chunk_sha256,
    observed_content_length,
    transport_url
) VALUES (
    'ipfs://QmZYVVP2XMNK2mjcrac6zyocvAU9xuEupZ4zYuoPVuimr7/borgormachinelowpoly.vrm',
    '2026-08-11T20:16:07Z',
    'recursive-crawler-2',
    '0.x',
    '{"title":"undefined","version":"undefined","author":"undefined","contactInformation":"undefined","reference":"undefined","allowedUserName":"OnlyAuthor","violentUssageName":"Disallow","sexualUssageName":"Disallow","commercialUssageName":"Disallow","otherPermissionUrl":"undefined","licenseName":"Redistribution_Prohibited","otherLicenseUrl":"undefined"}',
    NULL,
    1698236,
    '1d4658fb562972b6d045f161f9e16b921063b3222039f231e1d79c93dfacb8c4',
    '338795f2fe3b29cbd51fc0d5fd34a4e9a6a6424570e633b695fd7b0826593439',
    1698236,
    'https://ipfs.io/ipfs/QmZYVVP2XMNK2mjcrac6zyocvAU9xuEupZ4zYuoPVuimr7/borgormachinelowpoly.vrm'
)
ON CONFLICT(source_url) DO UPDATE SET
    extracted_at = excluded.extracted_at,
    extractor_version = excluded.extractor_version,
    vrm_spec = excluded.vrm_spec,
    vrm_meta_json = excluded.vrm_meta_json,
    parse_error = excluded.parse_error,
    content_length = excluded.content_length,
    content_sha256 = excluded.content_sha256,
    json_chunk_sha256 = excluded.json_chunk_sha256,
    observed_content_length = excluded.observed_content_length,
    transport_url = excluded.transport_url;
